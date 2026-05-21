from datetime import datetime


def log_interaction(user_input, system_output, intent, attempt):
    """
    Saves user interaction data into app.log
    """

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open("app.log", "a") as log_file:
        log_file.write(f"[{timestamp}]\n")
        log_file.write(f"USER INPUT: {user_input}\n")
        log_file.write(f"SYSTEM OUTPUT: {system_output}\n")
        log_file.write(f"INTENT: {intent}\n")
        log_file.write(f"ATTEMPT: {attempt}\n")
        log_file.write("-" * 50 + "\n")