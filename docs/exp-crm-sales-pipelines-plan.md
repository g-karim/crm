# EXP CRM Sales Pipelines Plan

## Context

EXP CRM is based on Frappe CRM, but it is intended to work as a branded business CRM for EXP Omniverse. One of the first required product changes is support for multiple sales pipelines, similar to amoCRM/Kommo, HubSpot, Zoho CRM, and Bitrix24.

The current Frappe CRM model is simpler:

- `CRM Lead` has a global `status`.
- `CRM Deal` has a global `status`.
- `CRM Lead Status` and `CRM Deal Status` are global status dictionaries.
- Kanban columns are generated from a selected field, usually `status`.
- Dragging a card in kanban updates that selected field.

This works for one generic sales process, but it does not support independent sales processes with their own stages, such as:

- B2C house kits
- B2B house kits
- Agencies
- Realtors
- Conditional refusal flows

The target is to add configurable deal pipelines without making lead management confusing.

## Product Decision

Do not create full "sales pipelines" for leads in v1.

Leads should remain a shared intake and qualification workspace:

- Source answers: where did the request come from?
- Lead status answers: where is it in qualification?
- Planned deal pipeline answers: which sales process will the future deal use?

Deals should use full sales pipelines:

- Pipeline answers: which business process is this sale in?
- Deal stage/status answers: where is this deal inside that process?

This avoids creating two competing systems for leads:

- lead source
- lead status
- lead pipeline

Instead, leads get one optional routing field that affects conversion to deal.

## Current Lead To Deal Behavior

In current Frappe CRM, converting a lead to a deal does the following:

1. Checks write permission for the lead.
2. Sets the lead status to `Qualified`, if that status exists.
3. Sets `converted = 1`.
4. Updates communication status to `Replied` if SLA conditions apply.
5. Creates or links Contact.
6. Creates or links Organization.
7. Creates `CRM Deal`.
8. Redirects the user to the new deal.

The leads list and leads kanban currently pass this default filter:

```js
{ converted: 0 }
```

So converted leads disappear from the active leads list/kanban. A lead converted from "Contacted" to a deal becomes `Qualified` internally, but it is hidden because `converted = 1`.

We should keep this behavior. Converted leads should not keep appearing in the active lead kanban, otherwise users see the same business opportunity in two places: once as a lead and once as a deal.

## Target User Model

### Leads

Leads are requests, first contacts, and qualification items.

Default lead kanban:

```text
New -> Contacting -> Contacted -> Qualified -> Unqualified / On Hold
```

The exact labels can be translated or adjusted, but the important point is that lead statuses stay global.

Lead segmentation should be handled by:

- `source`
- owner
- territory
- industry
- quick filters
- saved views
- optional planned deal pipeline

Example saved views:

- Leads from Avito
- Website leads
- Calls
- Leads for B2B direction

### Deals

Deals are real sales opportunities.

Deals must belong to a sales pipeline.

Example deal pipelines:

```text
B2C House Kits
B2B House Kits
Agencies
Realtors
EcoWool
```

Each deal pipeline has its own stages.

Example:

```text
B2C House Kits:
New deal -> Needs analysis -> Quote -> Contract -> Payment -> Won / Lost

B2B House Kits:
New deal -> Qualification -> Technical discussion -> Commercial proposal -> Legal review -> Won / Lost
```

## Data Model

### New DocType: CRM Sales Pipeline

Purpose: configurable sales pipelines for deals.

Suggested fields:

```text
pipeline_name / title
enabled
is_default
position
color
icon
description
archived
```

Notes:

- v1 uses this for deals only.
- The UI label should be "Sales Pipelines" / "Воронки продаж".
- There should be exactly one default enabled pipeline.
- Pipelines with existing deals should be archived instead of hard-deleted.

### Extend CRM Deal Status

`CRM Deal Status` becomes a pipeline stage.

Current limitation:

- `CRM Deal Status` uses `autoname = field:deal_status`.
- `deal_status` is unique.
- This prevents duplicate stage labels across pipelines.

Target:

```text
name: stable technical ID
deal_status: user-visible stage title
pipeline: Link to CRM Sales Pipeline
type: Open / Ongoing / On Hold / Won / Lost
probability
color
position
is_default
archived
```

Important:

- Existing status records keep their current names for migration safety.
- New records should use generated stable IDs, not the visible title.
- Remove global uniqueness from the visible title.
- Enforce uniqueness at application level for `(pipeline, deal_status)` instead.
- UI must display `deal_status`, not technical `name`, wherever possible.

Why not create a completely new `CRM Deal Stage` DocType?

- Frappe CRM already references `CRM Deal Status` in many places.
- `CRM Deal.status` already links to `CRM Deal Status`.
- Forecasting, lost reason logic, status color, probability, and status change logs already depend on this DocType.
- Reusing and evolving `CRM Deal Status` is less invasive than replacing the status field everywhere.

### Extend CRM Deal

Add:

```text
pipeline: Link to CRM Sales Pipeline, required
```

Keep:

```text
status: Link to CRM Deal Status
```

Validation rules:

- If `pipeline` is missing, set it to the default enabled sales pipeline.
- If `status` is missing, set it to the default/first open stage of the selected pipeline.
- If `status` is set, it must belong to the selected `pipeline`.
- If `pipeline` changes and the current `status` does not belong to the new pipeline, reset status to the default/first open stage of the new pipeline.
- `Won` and `Lost` behavior continues to use `CRM Deal Status.type`.

### Extend CRM Lead

Add:

```text
planned_deal_pipeline: Link to CRM Sales Pipeline, optional
```

UI label:

```text
Planned Deal Pipeline
Планируемая воронка сделки
```

Rules:

- Optional on lead creation.
- Should not be confused with a lead pipeline.
- Can be set by user, API, import, lead source integration, or web form.
- Used as a default when converting the lead to a deal.

### Lead Statuses

Do not make `CRM Lead Status` pipeline-specific in v1.

Keep existing global statuses.

Reasons:

- Lead statuses describe qualification progress, not sales process.
- Lead source and saved views already cover intake segmentation.
- Adding lead pipelines creates a confusing overlap with source and deal pipeline.
- Lead conversion already hides converted leads from active kanban via `converted = 1`.

## Standard Status Migration

### Deal Statuses

Create a default sales pipeline:

```text
Default Deal Pipeline
```

Assign every existing `CRM Deal Status` to this default pipeline.

Assign every existing `CRM Deal` to this default pipeline.

Existing status links remain valid.

Existing default statuses become the stages of the default pipeline, for example:

```text
Qualification
Demo/Making
Proposal/Quotation
Negotiation
Ready to Close
Won
Lost
```

Do not delete or hard-reset existing statuses.

### Lead Statuses

Leave existing lead statuses global.

Existing leads do not need a planned pipeline unless imported or manually assigned.

Converted lead behavior remains:

```text
status = Qualified
converted = 1
```

The lead disappears from the active leads kanban because active leads are filtered by `converted = 0`.

## Lead To Deal Conversion

### Current Behavior To Preserve

When a lead is converted:

```text
Lead.status = Qualified
Lead.converted = 1
Create CRM Deal
Redirect to deal
```

Keep this behavior.

### New Pipeline Behavior

During conversion:

```text
if Lead.planned_deal_pipeline is set:
    Deal.pipeline = Lead.planned_deal_pipeline
else:
    user selects Deal.pipeline in Convert to Deal modal

Deal.status = default/first open stage of Deal.pipeline
```

If the conversion modal includes the status field, its options must be filtered by the selected pipeline.

Recommended UX:

- Show a pipeline selector near the top of the Convert to Deal modal.
- Preselect from `Lead.planned_deal_pipeline`.
- If missing, preselect default deal pipeline or require selection.
- After pipeline selection, show only stages from that pipeline.

## Kanban Behavior

### Leads Kanban

Keep one common leads kanban grouped by `status`.

Default filter remains:

```text
converted = 0
```

Users can create saved views for lead sources or routing:

```text
source = Avito
source = Website
planned_deal_pipeline = B2B House Kits
```

### Deals Kanban

Deals kanban should be pipeline-aware.

Behavior:

- A pipeline selector is visible on Deals.
- The selected pipeline filters deals by `pipeline`.
- Kanban columns are stages from the selected pipeline.
- Dragging a deal card changes `status`, not `pipeline`.
- A deal cannot be moved into a stage from another pipeline.

If no pipeline is selected:

- Default list view may show all deals.
- Kanban should select the default pipeline or prompt for a pipeline.
- Avoid showing all stages from all pipelines in one kanban.

### Saved Views

Saved views should still work.

Pipeline can be part of the saved view filters:

```text
pipeline = B2C House Kits
```

For public/pinned views, this gives amoCRM-like left-side pipeline shortcuts without hardcoding.

## Settings UI

Add a manager-only settings section:

```text
Settings -> Sales Processes
```

or:

```text
Settings -> Sales Pipelines
```

Suggested layout:

- first screen: full-width list of pipelines
- second screen: full-width selected pipeline editor
- pipeline properties should stay compact so stages get most of the space

Pipeline actions:

- create pipeline
- rename pipeline
- set default
- enable/disable
- archive
- reorder
- duplicate pipeline

Stage actions:

- create stage
- rename stage
- set color
- set type
- set probability
- set default stage
- reorder via drag-and-drop
- archive stage

Stage type options:

```text
Open
Ongoing
On Hold
Won
Lost
```

Do not hardcode customer-specific pipelines or stages in code.

Every client must be able to configure pipelines and stages from the UI.

## Status Display

Because stage labels may repeat across pipelines, UI must distinguish:

```text
technical value: CRM Deal Status.name
visible label: CRM Deal Status.deal_status
context: CRM Deal Status.pipeline
```

Example:

```text
DEAL-STAGE-0001 -> "Quote" in B2C
DEAL-STAGE-0042 -> "Quote" in B2B
```

The user sees "Quote". The system stores `DEAL-STAGE-0001` or `DEAL-STAGE-0042`.

For dropdowns and kanban columns, show visible labels from the selected pipeline only.

## Optional Pipeline Rules

Do not implement strict HubSpot-like rules as mandatory v1 behavior.

HubSpot pipeline rules are useful for mature sales teams, but they can make early CRM adoption rigid.

Design the system so rules can be added later.

Recommended staged approach:

### v1

- Pipeline-specific stages.
- Backend validation that stage belongs to pipeline.
- Required lost reason still works for lost statuses.

### v1.5

Soft warnings:

- warn when skipping stages
- warn when moving backwards
- warn when closing without key fields

### v2

Optional hard rules per pipeline:

```text
prevent_skipping_stages
prevent_moving_backwards
required_fields_before_stage
allowed_roles_to_move_to_stage
require_approval_for_stage
```

Important:

- Rules must be enforced on backend, not only frontend.
- Managers/System Managers should be able to bypass or override rules where appropriate.

## amoCRM/Kommo Migration

amoCRM calls sales opportunities "leads", but they usually map better to `CRM Deal` in Frappe/EXP CRM because they already have:

- pipeline
- status/stage
- budget/value
- responsible user
- sales process state

Migration approach:

- amoCRM pipelines -> `CRM Sales Pipeline`
- amoCRM statuses -> `CRM Deal Status` under the matching pipeline
- amoCRM leads -> `CRM Deal`

Recommended custom trace fields:

```text
amo_pipeline_id
amo_status_id
amo_lead_id
```

Use these for audit, re-import, deduplication, and troubleshooting.

Only truly raw inquiries should become `CRM Lead`.

## Backend Touch Points

Expected backend changes:

- Add `CRM Sales Pipeline` DocType.
- Extend `CRM Deal Status`.
- Extend `CRM Deal`.
- Extend `CRM Lead`.
- Add migration patch for default pipeline and existing statuses/deals.
- Update `CRMDeal.validate_status`.
- Add `CRMDeal.validate_pipeline`.
- Update lead conversion to pass pipeline into new deal.
- Update create deal API to set default pipeline/status.
- Update kanban column generation for `CRM Deal.status` so it filters stages by selected pipeline.
- Update status option APIs/stores to support pipeline filtering.
- Update tests.

Important backend rule:

Frontend filtering is not enough. The backend must reject inconsistent data such as:

```text
Deal.pipeline = B2C
Deal.status = stage from B2B
```

## Frontend Touch Points

Expected frontend changes:

- Deals page:
  - pipeline selector
  - pipeline-aware kanban
  - pipeline-aware create deal defaults

- Deal form:
  - show/edit pipeline
  - status dropdown filtered by pipeline
  - reset status when pipeline changes

- Deal modal:
  - pipeline selector
  - status options filtered by pipeline

- Convert to Deal modal:
  - prefill pipeline from lead
  - require/select pipeline when missing
  - status options filtered by selected pipeline

- Leads:
  - add optional planned deal pipeline field
  - keep lead kanban global
  - allow filters/saved views by planned deal pipeline

- Settings:
  - sales pipeline manager UI

- Status store:
  - fetch deal statuses with pipeline field
  - group/cache by pipeline
  - map technical ID to visible title/color/type/probability

## Dashboard And Reporting

Existing dashboards that group deals by status need review.

Changes to consider:

- Add pipeline filter to deal stage dashboards.
- When grouping by status, display stage title.
- If viewing all pipelines together, stage labels can repeat, so include pipeline context where needed.
- Forecasting should use pipeline-specific stage probability.

Do not block v1 on advanced analytics, but avoid breaking current dashboards.

## Data Import And API

Data import should support:

```text
pipeline
status
```

Status imports should be validated:

- if status is provided without pipeline and status title is ambiguous, reject with clear error
- if pipeline is provided and status label is provided, resolve status within that pipeline
- if technical status ID is provided, validate it belongs to pipeline

API should accept technical IDs internally, but import UX should allow user-visible labels where possible.

## Update Strategy

The CRM app is now a fork:

```text
origin   https://github.com/g-karim/crm.git
upstream https://github.com/frappe/crm.git
```

The goal is to keep future upstream updates manageable, not to avoid all core changes at any cost.

Guidelines:

- Prefer additive schema changes where possible.
- Keep pipeline logic concentrated in small helpers/services.
- Avoid broad frontend rewrites.
- Patch existing components where the feature naturally belongs.
- Do not duplicate the whole kanban system.
- Backend validation is required even if frontend already filters.
- Commit changes in small feature-focused commits.
- Add tests for migration and critical behavior.
- Keep documentation updated with architectural decisions.

Expected upstream-sensitive files:

```text
frontend/src/pages/Deals.vue
frontend/src/pages/Deal.vue
frontend/src/pages/Lead.vue
frontend/src/components/Modals/DealModal.vue
frontend/src/components/Modals/ConvertToDealModal.vue
frontend/src/components/ViewControls.vue
frontend/src/components/Kanban/KanbanView.vue
frontend/src/stores/statuses.js
crm/api/doc.py
crm/fcrm/doctype/crm_deal/crm_deal.py
crm/fcrm/doctype/crm_lead/crm_lead.py
```

Upstream update workflow:

```bash
git fetch upstream
git checkout develop
git merge upstream/develop
bench setup requirements crm
bench build --app crm
bench --site v16.localhost migrate
```

Conflicts in the files above are expected and acceptable.

## Implementation Phases

### Phase 1: Backend Foundation

- Add `CRM Sales Pipeline`.
- Extend `CRM Deal Status` with `pipeline`, generated naming for new records, and display title support.
- Extend `CRM Deal` with required `pipeline`.
- Extend `CRM Lead` with optional `planned_deal_pipeline`.
- Add migration patch:
  - create default deal pipeline
  - attach existing deal statuses to it
  - attach existing deals to it
- Add backend validation for deal pipeline/status consistency.
- Add tests.

Phase 1 implementation status:

- Backend foundation is implemented in the EXP CRM fork.
- Clean test site `crm-pipeline-test.localhost` installs and migrates successfully with `frappe`, `erpnext`, `exp_theme`, `crm`, `frappe_assistant_core`, and `insights`.
- `CRM Sales Pipeline` tests pass.
- `CRM Deal Status` tests pass.
- Full `CRM Deal` test module passes.
- Full `CRM Lead` test module passes.

Test harness note:

- `CRM Deal` and `CRM Lead` tests use `UnitTestCase` instead of `IntegrationTestCase`.
- This avoids Frappe's automatic `make_test_records()` dependency recursion into unrelated ERPNext fixtures.
- The previous pre-test failure `DocType Payment Gateway not found` came from that external fixture graph, not from pipeline logic.
- The CRM tests still create and validate real Frappe documents against the test database.

### Phase 2: Deal Pipeline Kanban

- Add pipeline selector on Deals.
- Filter deals by selected pipeline.
- Generate kanban columns only from statuses in selected pipeline.
- Ensure drag-and-drop only changes status within selected pipeline.
- Ensure create deal from kanban uses selected pipeline and column stage.

Phase 2 implementation status:

- Deals page has a sales pipeline selector.
- The last selected deal pipeline is stored in the browser and reused on return.
- Deals list/group/kanban data is constrained by the selected `pipeline`.
- Deal kanban columns for `status` are generated from `CRM Deal Status` records in the selected pipeline.
- Kanban columns display the user-facing stage title `deal_status`, while drag-and-drop still writes the stable technical stage name.
- Creating a deal from the Deals page prefills the selected pipeline.
- Creating a deal from a kanban column prefills both selected pipeline and selected stage.
- Pipeline-mode kanban hides generic add/delete/reorder column controls; stage management belongs to the dedicated Sales Pipelines settings UI in Phase 4.
- Backend coverage includes a regression test proving that deal kanban columns and cards are limited to the selected pipeline.

### Phase 3: Deal Forms And Conversion

- Add pipeline field to deal form and modal.
- Filter status dropdown by pipeline.
- Update Lead -> Deal conversion:
  - prefill from `planned_deal_pipeline`
  - require or default pipeline when missing
  - set default stage from selected pipeline
- Keep lead converted behavior unchanged.

Phase 3 implementation status:

- Deal quick-entry modal now has a pipeline selector and filters the status dropdown by the selected pipeline.
- Deal detail page and mobile deal page now show/edit pipeline and keep status options limited to the deal pipeline.
- Changing a deal pipeline resets the status when the current stage belongs to another pipeline.
- Convert to Deal modal now preselects pipeline from `Lead.planned_deal_pipeline`, falling back to the default enabled sales pipeline.
- Convert to Deal modal filters deal stages by selected pipeline and keeps the default stage in sync.
- Install/migration layout helper adds `pipeline` and `planned_deal_pipeline` into default CRM Fields Layouts idempotently, without overwriting customized layouts.
- Existing lead conversion behavior is preserved: converted leads still get `converted = 1` and disappear from active lead views.

Phase 3 verification:

- `bench --site crm-pipeline-test.localhost run-tests --module crm.fcrm.doctype.crm_deal.test_crm_deal --test-category all` passes.
- `bench --site crm-pipeline-test.localhost run-tests --module crm.fcrm.doctype.crm_lead.test_crm_lead --test-category all` passes.
- `yarn build` passes for the CRM frontend.
- `bench --site v16.localhost migrate` applies `crm.patches.v1_0.add_sales_pipeline_fields_to_layouts` successfully.

### Phase 4: Settings UI

- Add Settings -> Sales Pipelines.
- Build pipeline list/editor.
- Build stage editor with reorder, color, type, probability.
- Support archive instead of destructive deletion when records exist.

Phase 4 implementation status:

- Added `Settings -> Sales Pipelines` for CRM managers.
- Built a two-step pipeline manager:
  - first screen lists pipelines with default/archived/disabled indicators and deal/stage counts
  - opening a pipeline shows a full-width editor for that pipeline
  - pipeline properties are compact, while stages get the main workspace
- Built a full-width stage editor for the selected pipeline:
  - create stages
  - edit stage title, type, probability, color, and position
  - reorder stages with up/down controls
  - archive/restore stages
- Added pipeline duplicate action that copies active stages into the new pipeline.
- Removed direct archive toggles from the editor; pipeline/stage archive actions now use confirmation dialogs.
- Added backend API layer in `crm.api.sales_pipeline` so the UI does not depend on scattered low-level document calls.
- Added `archived` to `CRM Deal Status`; active kanban/status dropdowns now ignore archived stages.
- Added API regression coverage for settings visibility and pipeline duplication.

Phase 4 verification:

- `bench --site crm-pipeline-test.localhost migrate` passes.
- `bench --site crm-pipeline-test.localhost run-tests --module crm.fcrm.doctype.crm_sales_pipeline.test_crm_sales_pipeline --test-category all` passes.
- `bench --site crm-pipeline-test.localhost run-tests --module crm.fcrm.doctype.crm_deal_status.test_crm_deal_status --test-category all` passes.
- `bench --site crm-pipeline-test.localhost run-tests --module crm.fcrm.doctype.crm_deal.test_crm_deal --test-category all` passes.
- `bench --site crm-pipeline-test.localhost run-tests --module crm.fcrm.doctype.crm_lead.test_crm_lead --test-category all` passes.
- `yarn build` passes for the CRM frontend.
- `bench --site v16.localhost migrate` passes.

### Phase 5: Migration And Import Support

- Add amoCRM mapping fields if needed.
- Add import handling for pipeline/stage.
- Add duplicate label handling.
- Add user-facing validation errors.

Phase 5 implementation status:

- Added amoCRM trace fields:
  - `CRM Sales Pipeline.amo_pipeline_id`
  - `CRM Deal Status.amo_status_id`
  - `CRM Deal Status.amo_pipeline_id`
  - `CRM Deal.amo_pipeline_id`
  - `CRM Deal.amo_status_id`
  - `CRM Deal.amo_lead_id`
- Added hidden deal import helper fields:
  - `CRM Deal.pipeline_label`
  - `CRM Deal.status_label`
- Deal import normalization now resolves:
  - technical pipeline IDs
  - pipeline labels through `pipeline_label`
  - amoCRM pipeline IDs through `amo_pipeline_id`
  - technical stage IDs
  - stage labels through `status_label`
  - amoCRM status IDs through `amo_status_id`
- Stage labels are resolved inside the selected deal pipeline.
- If a stage label is used without pipeline context and the same label exists in multiple pipelines, import fails with a clear validation error.
- `amo_lead_id` is unique across deals to support deduplication and repeat-import troubleshooting.
- `amo_pipeline_id` is unique across sales pipelines.
- `amo_status_id` is unique inside a sales pipeline.
- Deal stages inherit `amo_pipeline_id` from their sales pipeline when possible.
- Migration patch reloads the updated DocTypes and restores a default enabled sales pipeline if the site has none.

Phase 5 CSV guidance:

- For technical imports, use `pipeline` and `status` with stored document IDs.
- For user-facing amoCRM-style imports, use `pipeline_label` and `status_label`.
- For repeatable amoCRM imports, include `amo_pipeline_id`, `amo_status_id`, and `amo_lead_id`.
- If `status_label` is duplicated across pipelines, include `pipeline_label` or `amo_pipeline_id`.

### Phase 6: Rules And Advanced Process Control

- Add optional soft warnings.
- Later add hard rules per pipeline.
- Add role-based stage restrictions only when needed.

## Acceptance Criteria

- Existing CRM data remains usable after migration.
- Existing default deal kanban still works using the default pipeline.
- Users can create multiple deal pipelines from UI.
- Each pipeline can have independent stages.
- Deals cannot have a stage from another pipeline.
- Leads do not have full pipelines.
- Leads can optionally store planned deal pipeline.
- Lead conversion creates a deal in the correct pipeline.
- Converted leads disappear from active lead kanban as before.
- Pipeline/stage setup requires no code changes per client.
- The fork remains updateable from upstream with manageable conflicts.

## Open Decisions

- Exact Russian labels:
  - "Воронки продаж"
  - "Направление сделки"
  - "Планируемая воронка сделки"
  - "Готов к сделке" vs "Квалифицирован"

- Whether the Deals page should default to:
  - default pipeline kanban
  - last selected pipeline per user
  - all deals list view

- Whether to implement `CRM Sales Pipeline` only for deals in v1 or include a future-proof `applies_to` field.

- Whether pipeline-specific field layouts should be v1 or later.

Recommended v1 choice:

- Deals default to the user's last selected pipeline, falling back to the default pipeline.
- `CRM Sales Pipeline` can include an internal `applies_to = "CRM Deal"` field for future flexibility, but UI exposes only deal pipelines.
- Pipeline-specific field layouts are deferred.
