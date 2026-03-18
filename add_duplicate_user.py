
from app.database import get_connection

def add_duplicate_user():
    mobile = "8077043887"
    fname = "Test"
    lname = "Student"
    email = "student@example.com" # Different email
    position = "Student"
    is_admin = 0 # Not an admin
    password = "student_password"
    rollno = "5678"
    course = "PhD"
    department = "Physics"
    supervisor = "Dr. Smith"
    cosupervisor = "None"
    project_first = "Research"
    date = "2024-03-15"
    time = "11:00:00"
    log_in = "app"
    expiry_date = "12/31/2030"
    guide_app_by = "Admin"
    guide_app_date = "2024-03-15 11:00:00"
    admin_app_by = "Admin"
    admin_app_date = "2024-03-15 11:00:00"
    research_area = "Quantum"
    cenlevel = 0
    inuplevel = 0
    ncprelevel = 0
    websitelink = ""

    conn = get_connection()
    if not conn:
        print("Could not connect to database.")
        return

    try:
        with conn.cursor() as cursor:
            # We skip the "mobile already exists" check to create a duplicate
            query = """
            INSERT INTO login (
                email, password, fname, lname, position, is_admin, rollno, course, department,
                supervisor, cosupervisor, project_first, mobile, date, time, log_in, expiry_date,
                guide_app_by, guide_app_date, admin_app_by, admin_app_date, research_area,
                cenlevel, inuplevel, ncprelevel, websitelink
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """
            cursor.execute(query, (
                email, password, fname, lname, position, is_admin, rollno, course, department,
                supervisor, cosupervisor, project_first, mobile, date, time, log_in, expiry_date,
                guide_app_by, guide_app_date, admin_app_by, admin_app_date, research_area,
                cenlevel, inuplevel, ncprelevel, websitelink
            ))
        conn.commit()
        print(f"✅ Successfully added SECOND user {fname} {lname} with the SAME mobile {mobile}!")
    except Exception as e:
        print(f"❌ Error adding duplicate user: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_duplicate_user()
