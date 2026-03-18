
from app.database import get_connection

def add_specific_user():
    mobile = "8077043887"
    fname = "Astitva"
    lname = "Aryan"
    email = "astitva@example.com"
    position = "Developer"
    is_admin = 1 # Marking as admin for full access
    password = "dummy_password"
    rollno = "1234"
    course = "BTech"
    department = "IT"
    supervisor = "None"
    cosupervisor = "None"
    project_first = "Chatbot"
    date = "2024-03-15"
    time = "10:00:00"
    log_in = "app"
    expiry_date = "12/31/2030"
    guide_app_by = "Admin"
    guide_app_date = "2024-03-15 10:00:00"
    admin_app_by = "Admin"
    admin_app_date = "2024-03-15 10:00:00"
    research_area = "AI"
    cenlevel = 1
    inuplevel = 1
    ncprelevel = 1
    websitelink = ""

    conn = get_connection()
    if not conn:
        print("Could not connect to database.")
        return

    try:
        with conn.cursor() as cursor:
            # Check if user already exists
            cursor.execute("SELECT memberid FROM login WHERE mobile = %s", (mobile,))
            if cursor.fetchone():
                print(f"User with mobile {mobile} already exists!")
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
        print(f"✅ Successfully added {fname} {lname} with mobile {mobile} to the database!")
    except Exception as e:
        print(f"❌ Error adding user: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_specific_user()
