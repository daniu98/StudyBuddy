def login_placeholder(client):
    client.get("/")
    client.post(
        "/signup",
        data={
            "name": "blah",
            "email": "blah@blah",
            "password": "Placeholder",
        },
    )


def check_redirect(response, intended_redirect):
    return len(response.history) == 1 and response.request.path == intended_redirect


def signup_user(client, name, email, password="Placeholder"):
    client.get("/")
    return client.post(
        "/signup",
        data={"name": name, "email": email, "password": password},
        follow_redirects=True,
    )


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
