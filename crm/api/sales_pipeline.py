import frappe
from frappe import _

from crm.fcrm.doctype.crm_sales_pipeline.crm_sales_pipeline import get_default_deal_stage_templates
from crm.utils import is_frappe_version


PIPELINE_FIELDS = [
	"name",
	"pipeline_name",
	"external_source",
	"external_pipeline_id",
	"enabled",
	"is_default",
	"position",
	"color",
	"icon",
	"archived",
	"description",
	"enable_kanban_freeze_effect",
	"stage_skip_rule",
	"stage_backwards_rule",
	"closing_fields_rule",
	"warn_on_stage_skip",
	"warn_on_stage_backwards",
	"warn_on_closing_without_required_fields",
	"required_fields_before_closing",
]

STAGE_FIELDS = [
	"name",
	"deal_status",
	"pipeline",
	"external_source",
	"external_status_id",
	"external_pipeline_id",
	"type",
	"position",
	"probability",
	"color",
	"archived",
]

COUNT_NAME = (
	{"COUNT": "name", "as": "count"}
	if is_frappe_version("16", above=True)
	else "count(name) as count"
)

ACTIVE_DEAL_STAGE_TYPES = ["Open", "Ongoing", "On Hold"]


def check_manager_permission():
	if "System Manager" not in frappe.get_roles() and "Sales Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted"), frappe.PermissionError)


def can_force_archive_pipeline():
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


@frappe.whitelist()
def get_pipeline_settings(show_archived: bool = False):
	check_manager_permission()

	pipeline_filters = {}
	if not frappe.utils.cint(show_archived):
		pipeline_filters["archived"] = 0

	pipelines = frappe.get_all(
		"CRM Sales Pipeline",
		fields=PIPELINE_FIELDS,
		filters=pipeline_filters,
		order_by="position asc, modified asc",
	)

	pipeline_names = [pipeline.name for pipeline in pipelines]
	if not pipeline_names:
		return {
			"pipelines": pipelines,
			"stages": [],
			"deal_counts": {},
			"stage_deal_counts": {},
			"active_deal_counts": {},
			"can_force_archive": can_force_archive_pipeline(),
		}

	stage_filters = {}
	stage_filters["pipeline"] = ["in", pipeline_names]
	if not frappe.utils.cint(show_archived):
		stage_filters["archived"] = 0

	stages = frappe.get_all(
		"CRM Deal Status",
		fields=STAGE_FIELDS,
		filters=stage_filters,
		order_by="pipeline asc, position asc, modified asc",
	)

	deal_counts = frappe.get_all(
		"CRM Deal",
		fields=["pipeline", COUNT_NAME],
		filters={"pipeline": ["in", pipeline_names]},
		group_by="pipeline",
	)

	stage_deal_counts = []
	stage_names = [stage.name for stage in stages]
	if stage_names:
		stage_deal_counts = frappe.get_all(
			"CRM Deal",
			fields=["status", COUNT_NAME],
			filters={"status": ["in", stage_names]},
			group_by="status",
		)

	return {
		"pipelines": pipelines,
		"stages": stages,
		"deal_counts": {row.pipeline: row.count for row in deal_counts},
		"stage_deal_counts": {row.status: row.count for row in stage_deal_counts},
		"active_deal_counts": get_active_deal_counts(pipeline_names),
		"can_force_archive": can_force_archive_pipeline(),
	}


@frappe.whitelist()
def get_default_stage_templates():
	check_manager_permission()
	return get_default_deal_stage_templates()


@frappe.whitelist()
def save_pipeline(pipeline: dict):
	check_manager_permission()
	pipeline = frappe._dict(frappe.parse_json(pipeline))

	if pipeline.get("name"):
		doc = frappe.get_doc("CRM Sales Pipeline", pipeline.name)
	else:
		doc = frappe.new_doc("CRM Sales Pipeline")

	for field in PIPELINE_FIELDS:
		if field != "name" and field in pipeline:
			doc.set(field, pipeline.get(field))

	if not doc.position:
		doc.position = get_next_position("CRM Sales Pipeline")

	doc.save()
	return frappe.get_doc("CRM Sales Pipeline", doc.name).as_dict()


@frappe.whitelist()
def archive_pipeline(name: str, archived: bool = True, force: bool = False):
	check_manager_permission()
	doc = frappe.get_doc("CRM Sales Pipeline", name)
	doc.archived = frappe.utils.cint(archived)

	if doc.archived:
		active_deals = get_active_deal_count(doc.name)
		if active_deals and not frappe.utils.cint(force):
			frappe.throw(
				_(
					"Pipeline {0} has {1} active deals. Move them to Won/Lost stages or another pipeline before archiving."
				).format(frappe.bold(doc.pipeline_name), frappe.bold(active_deals)),
				frappe.ValidationError,
			)
		if active_deals and not can_force_archive_pipeline():
			frappe.throw(
				_("Only System Manager or Administrator can force archive a pipeline with active deals."),
				frappe.PermissionError,
			)

	if doc.archived:
		doc.enabled = 0
	else:
		doc.enabled = 1
	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def duplicate_pipeline(name: str, pipeline_name: str):
	check_manager_permission()
	source = frappe.get_doc("CRM Sales Pipeline", name)

	pipeline = frappe.new_doc("CRM Sales Pipeline")
	pipeline.pipeline_name = pipeline_name
	pipeline.enabled = 1
	pipeline.is_default = 0
	pipeline.position = get_next_position("CRM Sales Pipeline")
	pipeline.color = source.color
	pipeline.icon = source.icon
	pipeline.description = source.description
	pipeline.enable_kanban_freeze_effect = source.enable_kanban_freeze_effect
	pipeline.stage_skip_rule = source.stage_skip_rule
	pipeline.stage_backwards_rule = source.stage_backwards_rule
	pipeline.closing_fields_rule = source.closing_fields_rule
	pipeline.warn_on_stage_skip = source.warn_on_stage_skip
	pipeline.warn_on_stage_backwards = source.warn_on_stage_backwards
	pipeline.warn_on_closing_without_required_fields = source.warn_on_closing_without_required_fields
	pipeline.required_fields_before_closing = source.required_fields_before_closing
	pipeline.insert()

	for stage in frappe.get_all(
		"CRM Deal Status",
		fields=STAGE_FIELDS,
		filters={"pipeline": source.name, "archived": 0},
		order_by="position asc, modified asc",
	):
		new_stage = frappe.new_doc("CRM Deal Status")
		new_stage.deal_status = stage.deal_status
		new_stage.pipeline = pipeline.name
		new_stage.type = stage.type
		new_stage.position = stage.position
		new_stage.probability = stage.probability
		new_stage.color = stage.color
		new_stage.insert()

	return pipeline.as_dict()


@frappe.whitelist()
def save_stage(stage: dict):
	check_manager_permission()
	stage = frappe._dict(frappe.parse_json(stage))

	if stage.get("name"):
		doc = frappe.get_doc("CRM Deal Status", stage.name)
	else:
		doc = frappe.new_doc("CRM Deal Status")

	for field in STAGE_FIELDS:
		if field != "name" and field in stage:
			doc.set(field, stage.get(field))

	if not doc.position:
		doc.position = get_next_position("CRM Deal Status", {"pipeline": doc.pipeline})

	doc.save()
	return frappe.get_doc("CRM Deal Status", doc.name).as_dict()


@frappe.whitelist()
def archive_stage(name: str, archived: bool = True, force: bool = False):
	check_manager_permission()
	doc = frappe.get_doc("CRM Deal Status", name)
	doc.archived = frappe.utils.cint(archived)

	if doc.archived and doc.type in ACTIVE_DEAL_STAGE_TYPES:
		active_deals = get_active_deal_count_for_stage(doc.name)
		if active_deals and not frappe.utils.cint(force):
			frappe.throw(
				_(
					"Stage {0} has {1} active deals. Move them to Won/Lost stages or another stage before archiving."
				).format(frappe.bold(doc.deal_status), frappe.bold(active_deals)),
				frappe.ValidationError,
			)
		if active_deals and not can_force_archive_pipeline():
			frappe.throw(
				_("Only System Manager or Administrator can force archive a stage with active deals."),
				frappe.PermissionError,
			)

	doc.save()
	return doc.as_dict()


@frappe.whitelist()
def reorder_pipelines(names: list[str]):
	check_manager_permission()
	names = frappe.parse_json(names)
	for position, name in enumerate(names, start=1):
		frappe.db.set_value("CRM Sales Pipeline", name, "position", position, update_modified=False)


@frappe.whitelist()
def reorder_stages(pipeline: str, names: list[str]):
	check_manager_permission()
	names = frappe.parse_json(names)
	for position, name in enumerate(names, start=1):
		frappe.db.set_value(
			"CRM Deal Status",
			{"name": name, "pipeline": pipeline},
			"position",
			position,
			update_modified=False,
		)


def get_next_position(doctype: str, filters: dict | None = None):
	last = frappe.get_all(
		doctype,
		fields=["position"],
		filters=filters or {},
		order_by="position desc",
		limit=1,
	)
	return (frappe.utils.cint(last[0].position) if last else 0) + 1


def get_active_deal_count(pipeline: str):
	return get_active_deal_counts([pipeline]).get(pipeline, 0)


def get_active_deal_counts(pipelines: list[str]):
	if not pipelines:
		return {}

	active_stages = frappe.get_all(
		"CRM Deal Status",
		fields=["name"],
		filters={
			"pipeline": ["in", pipelines],
			"type": ["in", ACTIVE_DEAL_STAGE_TYPES],
		},
	)
	active_stage_names = [stage.name for stage in active_stages]
	if not active_stage_names:
		return {}

	counts = frappe.get_all(
		"CRM Deal",
		fields=["pipeline", COUNT_NAME],
		filters={
			"pipeline": ["in", pipelines],
			"status": ["in", active_stage_names],
		},
		group_by="pipeline",
	)
	return {row.pipeline: row.count for row in counts}


def get_active_deal_count_for_stage(stage: str):
	return frappe.db.count(
		"CRM Deal",
		{
			"status": stage,
		},
	)
