# Fix for timer interval sync issue
# Replace line 314 in simple_dashboard.py with these lines:

OLD_LINE_314 = "const timeLeft = Math.max(0, 30 - (timeSinceStart % 30));"

NEW_LINES_314_315 = """const intervalSeconds = dcaSettings.interval * 60; // Convert minutes to seconds
                        const timeLeft = Math.max(0, intervalSeconds - (timeSinceStart % intervalSeconds));"""

print("Replace line 314 in simple_dashboard.py:")
print(f"OLD: {OLD_LINE_314}")
print(f"NEW: {NEW_LINES_314_315}")

