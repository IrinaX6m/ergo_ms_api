from src.external.crm.models import Section,Task
def get_users(user_id: int):
    return tuple(
        [
            """
            select
                id,
                username,
                email,
                first_name,
                last_name
            from
                auth_user
            where id = %s
            """,
            tuple([user_id]),
        ]
    )
def get_users_count():
    return (
      """
        select
            name
        from
            student
        """,
        tuple(),
    )
def get_students():
    return tuple ([
            """
            select
                name
            from
                student
            """,
            tuple(),
    ])

#CRM
def get_sections_and_tasks():
    return (
        """
        SELECT
        s.id AS section_id,
        s.name AS section_name,
        p.id AS project_id,
        json_agg(json_build_object(
            'id', t.id,
            'text', t.text,
            'isdone', t.isdone,
            'description', t.description,
            'dateofcreation', t.dateofcreation,
            'deadline', t.deadline,
            'priority', t.priority,
            'parenttask_id', t.parenttask_id,
            'user_id', t.user_id
        )) AS tasks
        FROM
            crm_section s
        JOIN
            crm_project p ON s.project_id = p.id
        LEFT JOIN
            crm_task t ON s.id = t.section_id
        GROUP BY
            s.id, s.name, p.id
        ORDER BY
            s.id;
        """,
        tuple(),
    )

def add_new_section(section_name, project_id):
    return (
        """
        INSERT INTO crm_section (name, project_id)
        VALUES (%s, %s)
        RETURNING id, name, project_id;
        """,
        (section_name, project_id),
    )
def add_new_project(project_name, creator_id):
    return (
        """
        INSERT INTO crm_project (name, dateofcreation, creator_id)
        VALUES (%s, CURRENT_DATE, %s)
        RETURNING id, name, dateofcreation, creator_id;
        """,
        (project_name, creator_id),
    )
def add_new_task(task_data):
    # Базовые обязательные поля
    fields = ["text", "section_id"]
    values = [task_data["text"], task_data["section_id"]]
    
    # Добавляем опциональные поля, если они есть в task_data
    optional_fields = [
        "description", "deadline", "priority", 
        "parenttask_id", "user_id"
    ]
    
    for field in optional_fields:
        if field in task_data:
            fields.append(field)
            values.append(task_data[field])
    
    # Создаем SQL-запрос
    placeholders = ", ".join(["%s"] * len(fields))
    fields_str = ", ".join(fields)
    
    query = f"""
        INSERT INTO crm_task ({fields_str})
        VALUES ({placeholders})
        RETURNING id;
    """
    
    return (query, tuple(values))

def get_users_by_name(name: str):
    return tuple(
        [
            f"""
            select
                id,
                username,
                email,
                first_name,
                last_name
            from
                auth_user
            where username = {name}
            """,
            tuple([name]),
        ]
    )
