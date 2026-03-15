import sys
from app.database import get_connection

def add_user():
    mobile = "9894254006"
    fname = "Bala Krishnan"
    lname = "Unknown"
    email = "bala1@example.com"
    position = "Researcher"
    is_admin = 0
    password = "dummy_password"
    rollno = "0000"
    course = "Unknown"
    department = "General"
    supervisor = "Unknown"
    cosupervisor = "Unknown"
    project_first = "Unknown"
    date = "2024-01-01"
    time = "00:00:00"
    log_in = "app"
    expiry_date = "12/31/2030"
    guide_app_by = "Admin"
    guide_app_date = "2024-01-01 00:00:00"
    admin_app_by = "Admin"
    admin_app_date = "2024-01-01 00:00:00"
    research_area = "Unknown"
    cenlevel = 0
    inuplevel = 0
    ncprelevel = 0
    websitelink = ""

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Check if user already exists
            cursor.execute("SELECT memberid FROM login WHERE email = %s", (email,))
            if cursor.fetchone():
                print("User already exists!")
                return
            
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
        print(f"Successfully added {fname} with mobile {mobile} to the database!")
    except Exception as e:
        print(f"Error adding user: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_user()
