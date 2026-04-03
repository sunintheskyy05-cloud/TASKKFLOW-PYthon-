import unittest
import os
import sys
import json
from datetime import datetime

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from main import Task

class TestTask(unittest.TestCase):
    def test_task_creation(self):
        task = Task(title="Test Task", description="Test Description", priority="High")
        self.assertEqual(task.title, "Test Task")
        self.assertEqual(task.description, "Test Description")
        self.assertEqual(task.priority, "High")
        self.assertEqual(task.status, "To Do")
        self.assertIsNotNone(task.created_at)

    def test_task_to_dict(self):
        task = Task(title="Test", priority="Medium")
        task_dict = task.to_dict()
        self.assertIn("title", task_dict)
        self.assertIn("priority", task_dict)
        self.assertEqual(task_dict["title"], "Test")

    def test_priority_color(self):
        task_high = Task(priority="High")
        task_medium = Task(priority="Medium")
        task_low = Task(priority="Low")
        self.assertEqual(task_high.get_priority_color(), "#EF4444")  # DANGER_COLOR
        self.assertEqual(task_medium.get_priority_color(), "#F59E0B")  # WARNING_COLOR
        self.assertEqual(task_low.get_priority_color(), "#22C55E")  # SUCCESS_COLOR

if __name__ == '__main__':
    unittest.main()