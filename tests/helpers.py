def check_redirect(response, intended_redirect):
    return len(response.history) == 1 and response.request.path == intended_redirect


def signup_user(client, name, email, password="Placeholder"):
    client.get("/")
    return client.post(
        "/signup",
        data={"name": name, "email": email, "password": password},
        follow_redirects=True,
    )

def signup_user_playwright(webpage, name, email, password="Placeholder"):
    webpage.goto("http://localhost:5001")
    webpage.get_by_role("link", name = "Sign Up").click()
    webpage.get_by_role("textbox", name = "Name").fill(name)
    webpage.get_by_role("textbox", name = "Email").fill(email)
    webpage.get_by_role("textbox", name = "Password").fill(password)
    webpage.get_by_role("button", name = "Register").click()

def create_group(client, title, course_ids=None, max_members=8):
    data = {
        "title": title,
        "max_members": max_members,
        "location": "Powell Library",
        "study_style": "General study",
    }
    if course_ids:
        data["course_ids"] = course_ids
    return client.post("/study-groups/new", data=data, follow_redirects=True)

def create_group_playwright(webpage, group_name, courses={}, description="", max_members="8", location="Powell Library", date_time="2000-01-01T14:00"):
    webpage.get_by_role("link", name = "Create Group").click()
    webpage.get_by_role("textbox", name = "Title").fill(group_name)
    webpage.get_by_role("textbox", name = "Description").fill(description)
    webpage.get_by_text("Max members").fill(max_members)
    webpage.get_by_label("Meeting time").fill(date_time)
    webpage.get_by_role("textbox", name = "Location").fill(location)
    checkboxes = webpage.get_by_role("checkbox").all()
    for course_num in courses:
        checkboxes[course_num].click()
    webpage.get_by_role("button", name = "Create group").click()

def send_message(webpage, message):
    webpage.get_by_role("textbox").fill(message)
    webpage.get_by_role("button", name = "Send").click()

def count_num(webpage, html_class, desired_text):
    class_list = webpage.locator(html_class).all()
    count = 0
    for member in class_list:
        if not member.is_hidden():
            count += member.filter(has_text=desired_text).count()
    return count