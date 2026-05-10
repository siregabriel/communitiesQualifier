# Services Package

This package contains business logic and data management services for the Inspection System.

## QuestionManager

The `QuestionManager` class handles CRUD operations for inspection questions with JSON file-based persistence.

### Features

- Create, read, update, and delete (soft delete) inspection questions
- Community-based question filtering
- JSON file persistence with error handling
- Unique ID generation using timestamp and random numbers
- ISO 8601 timestamp formatting
- Input validation for question text and communities

### Usage Example

```python
from services.question_manager import QuestionManager

# Initialize with storage path
manager = QuestionManager('app_mantenimiento/data/questions.json')

# Create a question
question = manager.create_question(
    text="Is the common area clean?",
    photo_required=True,
    communities=["Community A", "Community B"]
)

# Get all active questions
active_questions = manager.get_all_active_questions()

# Get questions for a specific community
community_questions = manager.get_questions_for_community("Community A")

# Update a question
updated = manager.update_question(
    question_id=question['id'],
    text="Is the common area very clean?",
    photo_required=False,
    communities=["Community A", "Community C"]
)

# Soft delete a question
manager.delete_question(question['id'])
```

### Data Structure

Questions are stored in JSON format with the following structure:

```json
{
    "version": "1.0",
    "last_modified": "2024-01-15T10:30:00Z",
    "questions": [
        {
            "id": "q_1705315800000_5678",
            "text": "Is the common area clean?",
            "photo_required": true,
            "communities": ["Community A", "Community B"],
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:30:00Z",
            "is_active": true
        }
    ]
}
```

### Validation Rules

- **Question Text**: Must be non-empty after stripping whitespace
- **Communities**: Must be a non-empty array (empty array = inactive question)
- **ID**: Automatically generated and guaranteed unique
- **Timestamps**: ISO 8601 format, `created_at` is immutable, `updated_at` changes on edits

### Testing

Run the unit tests with:

```bash
python3 app_mantenimiento/services/question_manager.test.py
```

The test suite includes 24 tests covering:
- Question creation and validation
- CRUD operations
- Community filtering
- Soft delete behavior
- JSON persistence and error handling
- ID uniqueness
- Timestamp formatting
