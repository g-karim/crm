import frappe

from crm.demo.utils import backdate, resolve_owners


def create_demo_tasks(lead_names, demo_users):
	from datetime import date, datetime, timedelta

	today = date.today()
	now = datetime.now()
	session_user, owner_1, owner_2, _ = resolve_owners(demo_users)

	tasks_data = [
		{
			"title": "Отправить коммерческое предложение",
			"priority": "High",
			"status": "Todo",
			"assigned_to": session_user,
			"due_date": today + timedelta(days=2),
			"reference_doctype": "CRM Lead",
			"reference_docname": lead_names[0],
			"description": "Подготовить и отправить предложение с ценами, интеграциями и планом запуска.",
			"days_ago": 1,
		},
		{
			"title": "Запланировать техническую демонстрацию",
			"priority": "Medium",
			"status": "In Progress",
			"assigned_to": owner_1,
			"due_date": today + timedelta(days=5),
			"reference_doctype": "CRM Lead",
			"reference_docname": lead_names[0],
			"description": "Согласовать с техническим директором часовую демонстрацию продукта.",
			"days_ago": 3,
		},
		{
			"title": "Уточнить статус тестового доступа",
			"priority": "High",
			"status": "Todo",
			"assigned_to": owner_1,
			"due_date": today + timedelta(days=1),
			"reference_doctype": "CRM Lead",
			"reference_docname": lead_names[1],
			"description": "Проверить ход тестирования и закрыть вопросы до следующего звонка.",
			"days_ago": 2,
		},
		{
			"title": "Отправить сравнение с конкурентами",
			"priority": "Medium",
			"status": "Done",
			"assigned_to": owner_2,
			"due_date": today - timedelta(days=2),
			"reference_doctype": "CRM Lead",
			"reference_docname": lead_names[1],
			"description": "Отправить таблицу сравнения возможностей и преимуществ перед конкурентом.",
			"days_ago": 6,
		},
		{
			"title": "Настроить тестовое окружение",
			"priority": "High",
			"status": "In Progress",
			"assigned_to": owner_2,
			"due_date": today + timedelta(days=3),
			"reference_doctype": "CRM Lead",
			"reference_docname": lead_names[2],
			"description": "Подготовить тестовый стенд с примером данных для оценки командой клиента.",
			"days_ago": 3,
		},
		{
			"title": "Подтвердить детали годового плана",
			"priority": "Low",
			"status": "Backlog",
			"assigned_to": session_user,
			"due_date": today + timedelta(days=10),
			"reference_doctype": "CRM Lead",
			"reference_docname": lead_names[3],
			"description": "Согласовать количество пользователей и отправить обновленное предложение на год.",
			"days_ago": 1,
		},
	]

	created = []
	for data in tasks_data:
		owner = data["assigned_to"]
		ts = now - timedelta(days=data.pop("days_ago"))
		task = frappe.get_doc({"doctype": "CRM Task", **data}).insert(ignore_permissions=True)
		backdate("CRM Task", task.name, owner, ts)
		created.append(task.name)

	return created


def delete_demo_tasks(task_names):
	for name in task_names:
		if frappe.db.exists("CRM Task", name):
			frappe.delete_doc("CRM Task", name, ignore_permissions=True, force=True)
