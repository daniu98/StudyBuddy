from playwright.sync_api import expect

import os
from studybuddy.db import get_db

from tests.helpers import check_redirect, create_group, create_group_playwright, signup_user, signup_user_playwright, count_num


def test_signup_and_create_group_and_search_groups(webpage):
    signup_user_playwright(webpage, "Creator", "creator@example.com")

    webpage.get_by_role("link", name = "Find Groups").click()
    assert webpage.get_by_text("Create the first group").count()

    create_group_playwright(webpage, "Midterm Group", {0, 1}, "Suddenly, one day", "3", "Powell Library")

    webpage.get_by_role("link", name = "Find Groups").click()
    assert webpage.get_by_text("Midterm Group").count() and webpage.get_by_text("You are a member").count()
    assert webpage.get_by_text("MATH31a").count() and webpage.get_by_text("Computer Science").count()

    search_button = webpage.get_by_role("button", name = "Search")
    searchbox = webpage.get_by_role("searchbox")
    searchbox.fill("Midterm")
    search_button.click()
    assert count_num(webpage, ".dashboard-group-title", "Midterm") == 1, "text search includes group"
    assert webpage.get_by_text("Midterm Group").count() and webpage.get_by_text("You are a member").count()
    assert webpage.get_by_text("MATH31a").count() and webpage.get_by_text("Computer Science").count()
    assert not webpage.get_by_text("Join Group").count()
    searchbox.fill("Not")
    search_button.click()
    assert count_num(webpage, ".dashboard-group-title", "Midterm") == 0, "text search excludes group"

    webpage.get_by_text("Clear").click()
    dropdown = webpage.get_by_role("combobox")
    dropdown.select_option(value="1")
    search_button.click()
    assert count_num(webpage, ".dashboard-group-title", "Midterm") == 1, "course search includes group"
    assert webpage.get_by_text("Midterm Group").count() and webpage.get_by_text("members").count()
    assert webpage.get_by_text("MATH31a").count() and webpage.get_by_text("Computer Science").count()
    dropdown.select_option(value="3")
    search_button.click()
    assert count_num(webpage, ".dashboard-group-title", "Midterm") == 0, "course search includes group"
    assert not(webpage.get_by_text("Midterm Group").count() and webpage.get_by_text("members").count())

    conn = get_db()
    group = conn.execute(
        "SELECT id FROM study_groups WHERE title = 'Midterm Group' AND description = 'Suddenly, one day' AND max_members = 3 AND location = 'Powell Library'"
    ).fetchone()
    assert group is not None
    conn.close()



def test_join_and_group_page_and_message_flow(webpage):
    signup_user_playwright(webpage, "Owner", "owner@example.com")
    webpage.get_by_role("link", name = "Find Groups").click()
    create_group_playwright(webpage, "Shared Notes Group", {2})

    webpage.get_by_role("link", name = "Logout").click()
    signup_user_playwright(webpage, "Stock Member", "member@example.com")

    webpage.get_by_role("link", name = "Find Groups").click()
    webpage.get_by_role("button", name = "Join Group").click()

    assert webpage.get_by_text("Shared Notes Group").count() and webpage.get_by_text("admin").count() and webpage.get_by_text("owner").count()
    assert webpage.get_by_text("Members").count() and webpage.get_by_text("8").count()
    assert webpage.get_by_text("role: member").count()
    assert webpage.get_by_text("location").count() and webpage.get_by_text("Powell").count()
    assert webpage.get_by_text("Math 2").count()
    
    assert webpage.get_by_text("no messages").count()
    webpage.get_by_role("textbox").fill("Placeholder Unique Worded Message")
    webpage.get_by_role("button", name = "Send").click()
    assert count_num(webpage, ".group-messages", "Placeholder Unique Worded Message") == 1
    assert count_num(webpage, ".group-messages", "Stock Member") == 1

    webpage.get_by_role("link", name = "Dashboard").all()[0].click()
    assert webpage.get_by_text("Your Activity Snapshot").count()
    assert webpage.get_by_text("Shared Notes Group").count()


def test_group_review_flow(webpage):
    signup_user_playwright(webpage, "Reviewer", "reviewer@example.com")
    webpage.get_by_role("link", name = "Find Groups").click()
    create_group_playwright(webpage, "Review Target Group", {2})

    webpage.get_by_role("link", name = "Dashboard").click()
    webpage.get_by_role("link", name = "Review Target Group").click()
    webpage.get_by_role("link", name = "Group Reviews").click()
    dropdown = webpage.get_by_role("combobox")
    review_box = webpage.get_by_role("textbox", name = "Review")
    dropdown.select_option(value="1")
    review_box.fill("Very helpful group.")
    webpage.get_by_role("button", name = "Submit review").click()

    assert count_num(webpage, ".review-list", "Reviewer") == 1
    assert count_num(webpage, ".review-list", "Very helpful group.") == 1
    assert webpage.get_by_text("5").count()

    dropdown.select_option(value="3")
    review_box.fill("Acceptably helpful group.")
    webpage.get_by_role("button", name = "Update review").click()
    
    assert count_num(webpage, ".review-form-section", "Update your review") == 1
    assert count_num(webpage, ".review-list", "Reviewer") == 1
    assert count_num(webpage, ".review-list", "Acceptably helpful group.") == 1
    assert webpage.get_by_text("4").count()