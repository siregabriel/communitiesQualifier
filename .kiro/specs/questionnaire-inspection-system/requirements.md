# Requirements Document

## Introduction

This document specifies the requirements for transforming the existing maintenance report system into a questionnaire-based inspection system for 38 assisted living communities. The system will allow administrators to create and manage inspection questions through a user interface, and staff members to complete inspections by answering these questions with optional photo uploads. The system will continue using JSON file-based storage and maintain the existing authentication and community assignment structure.

## Glossary

- **Inspection_System**: The web application that manages questionnaire-based inspections for assisted living communities
- **Admin_User**: A user with administrative privileges who can create, edit, and delete inspection questions
- **Staff_User**: A user assigned to a specific community who completes inspections by answering questions
- **Question**: An inspection item that requires a response, consisting of text, optional photo requirement, and metadata
- **Inspection_Response**: A staff member's answer to a question, including condition rating, description, and optional photo
- **Question_Bank**: The collection of all questions available for inspections, stored in JSON format
- **Inspection_Submission**: A complete set of responses submitted by a staff member for a specific community
- **Question_Manager_UI**: The administrative interface for creating, editing, and managing questions
- **Inspection_Form**: The mobile-optimized interface where staff members answer questions
- **JSON_Storage**: File-based data persistence using JSON format for questions and responses

## Requirements

### Requirement 1: Question Management System

**User Story:** As an Admin_User, I want to create and manage inspection questions through a user interface, so that I can customize the inspection process without modifying code

#### Acceptance Criteria

1. THE Inspection_System SHALL provide a Question_Manager_UI accessible only to Admin_User accounts
2. WHEN an Admin_User creates a new question, THE Inspection_System SHALL store the question text, photo requirement flag, creation timestamp, and unique identifier in the Question_Bank
3. WHEN an Admin_User edits an existing question, THE Inspection_System SHALL update the question text and photo requirement while preserving the unique identifier and creation timestamp
4. WHEN an Admin_User deletes a question, THE Inspection_System SHALL remove the question from the Question_Bank and mark it as inactive rather than permanently deleting it
5. THE Inspection_System SHALL persist all Question_Bank data in JSON format within the file system
6. THE Inspection_System SHALL display all questions in the Question_Manager_UI with options to edit or delete each question
7. WHEN an Admin_User submits a question without text, THE Inspection_System SHALL display a validation error and prevent submission
8. THE Inspection_System SHALL assign a unique identifier to each question using timestamp-based generation

### Requirement 2: Community-Specific Question Assignment

**User Story:** As an Admin_User, I want to assign questions to specific communities, so that each community can have a customized inspection questionnaire

#### Acceptance Criteria

1. WHEN an Admin_User creates a new question, THE Inspection_System SHALL require selection of one or more communities to which the question applies
2. THE Inspection_System SHALL store community assignments as part of the question data in the Question_Bank
3. WHEN a Staff_User accesses the Inspection_Form, THE Inspection_System SHALL display only questions assigned to the user's community
4. THE Question_Manager_UI SHALL provide a community selector interface allowing Admin_User to assign questions to multiple communities simultaneously
5. WHEN an Admin_User edits a question, THE Inspection_System SHALL allow modification of community assignments without affecting the question text or other properties
6. THE Question_Manager_UI SHALL display the assigned communities for each question in the question list view
7. THE Inspection_System SHALL support assigning a single question to all 38 communities through a "Select All" option in the community selector
8. WHERE a question is assigned to zero communities, THE Inspection_System SHALL treat the question as inactive and SHALL NOT display it in any Inspection_Form

### Requirement 3: Flexible Inspection Completion

**User Story:** As a Staff_User, I want to skip questions during inspection, so that I can submit partial inspections when I cannot answer all questions

#### Acceptance Criteria

1. THE Inspection_System SHALL allow Staff_User to submit an Inspection_Submission without answering all questions
2. THE Inspection_System SHALL NOT mark any question as mandatory or required
3. WHEN a Staff_User submits an Inspection_Submission, THE Inspection_System SHALL save all answered questions and omit unanswered questions from the submission
4. THE Inspection_System SHALL display a visual indicator for unanswered questions but SHALL NOT prevent submission
5. WHEN a Staff_User skips a question, THE Inspection_System SHALL NOT store any data for that question in the Inspection_Submission

### Requirement 4: Question Response Interface

**User Story:** As a Staff_User, I want to answer inspection questions with condition ratings, descriptions, and photos, so that I can provide comprehensive inspection data

#### Acceptance Criteria

1. THE Inspection_Form SHALL display each question from the Question_Bank as a separate section with the question text
2. WHEN a Staff_User views a question, THE Inspection_Form SHALL provide radio buttons for "Good" and "Needs Attention" condition ratings
3. THE Inspection_Form SHALL provide a textarea input for description text for each question
4. WHERE a question has the photo requirement flag set to true, THE Inspection_Form SHALL display a photo upload button with camera access
5. WHERE a question has the photo requirement flag set to false, THE Inspection_Form SHALL NOT display a photo upload option
6. WHEN a Staff_User uploads a photo, THE Inspection_System SHALL validate the file type as an image format
7. WHEN a Staff_User uploads a photo, THE Inspection_System SHALL validate the file size does not exceed 16MB
8. THE Inspection_Form SHALL display a preview of uploaded photos before submission
9. THE Inspection_Form SHALL maintain the existing mobile-first responsive design with touch-optimized controls

### Requirement 5: Inspection Submission and Storage

**User Story:** As a Staff_User, I want to submit my inspection responses, so that they are saved and available for review

#### Acceptance Criteria

1. WHEN a Staff_User submits the Inspection_Form, THE Inspection_System SHALL create an Inspection_Submission containing all answered questions
2. THE Inspection_System SHALL store each Inspection_Response with the question identifier, condition rating, description text, photo file path, and timestamp
3. THE Inspection_System SHALL organize uploaded photos in community-specific folders within the uploads directory
4. THE Inspection_System SHALL generate unique filenames for photos using the format: username_community_timestamp.extension
5. THE Inspection_System SHALL persist Inspection_Submission data in JSON format within the file system
6. WHEN an Inspection_Submission is saved, THE Inspection_System SHALL include the Staff_User username, assigned community, and submission timestamp
7. THE Inspection_System SHALL display a success message to the Staff_User after successful submission
8. IF an Inspection_Submission fails to save, THEN THE Inspection_System SHALL display an error message and retain the form data

### Requirement 6: Question Manager UI Design

**User Story:** As an Admin_User, I want an intuitive interface for managing questions, so that I can efficiently create and maintain the inspection questionnaire

#### Acceptance Criteria

1. THE Question_Manager_UI SHALL display a list of all questions with their text and photo requirement status
2. THE Question_Manager_UI SHALL provide a "Create New Question" button that opens a form for question creation
3. THE Question_Manager_UI SHALL provide an "Edit" button for each question that opens a form pre-populated with existing question data
4. THE Question_Manager_UI SHALL provide a "Delete" button for each question with a confirmation dialog
5. THE Question_Manager_UI SHALL use the existing desktop-first design language consistent with the dashboard interface
6. THE Question_Manager_UI SHALL display questions in creation order with the newest questions at the top
7. THE Question_Manager_UI SHALL provide a checkbox input for the photo requirement flag in create and edit forms
8. WHEN an Admin_User saves a question, THE Question_Manager_UI SHALL close the form and refresh the question list

### Requirement 7: Authentication and Authorization

**User Story:** As the Inspection_System, I want to enforce role-based access control, so that only authorized users can manage questions

#### Acceptance Criteria

1. THE Inspection_System SHALL restrict access to the Question_Manager_UI to users with Admin_User role
2. WHEN a Staff_User attempts to access the Question_Manager_UI, THE Inspection_System SHALL redirect to the Inspection_Form
3. THE Inspection_System SHALL maintain the existing session-based authentication mechanism
4. THE Inspection_System SHALL maintain the existing user database structure with username, password, and community assignment
5. THE Inspection_System SHALL continue to use the existing login flow and session management

### Requirement 8: Data Migration and Compatibility

**User Story:** As a system administrator, I want the new questionnaire system to coexist with existing data structures, so that the transition is smooth and reversible

#### Acceptance Criteria

1. THE Inspection_System SHALL create a new JSON file for the Question_Bank separate from existing report data
2. THE Inspection_System SHALL create a new JSON file structure for Inspection_Submission data separate from existing report data
3. THE Inspection_System SHALL maintain the existing uploads folder structure for photo storage
4. THE Inspection_System SHALL NOT modify or delete existing maintenance report data during deployment
5. THE Inspection_System SHALL use the existing Flask application structure and routing patterns

### Requirement 9: Dashboard Integration

**User Story:** As an Admin_User, I want to view inspection submissions in the dashboard, so that I can review inspection results alongside the question management interface

#### Acceptance Criteria

1. THE Inspection_System SHALL display Inspection_Submission data in the existing dashboard card gallery layout
2. THE Inspection_System SHALL display each answered question as a separate card showing the question text, condition rating, description, and photo
3. THE Inspection_System SHALL apply the existing filter functionality to Inspection_Response cards based on condition rating
4. THE Inspection_System SHALL display the Staff_User username, community, and submission timestamp on each card
5. THE Inspection_System SHALL provide a navigation link from the dashboard to the Question_Manager_UI for Admin_User accounts

### Requirement 10: Mobile Optimization

**User Story:** As a Staff_User, I want the inspection form to work seamlessly on mobile devices, so that I can complete inspections efficiently in the field

#### Acceptance Criteria

1. THE Inspection_Form SHALL maintain mobile-first responsive design for all screen sizes
2. THE Inspection_Form SHALL use touch-optimized controls for radio buttons with minimum 44x44 pixel touch targets
3. WHEN a Staff_User accesses the photo upload on a mobile device, THE Inspection_System SHALL open the device camera with rear camera preference
4. THE Inspection_Form SHALL display questions in a scrollable vertical layout optimized for single-hand operation
5. THE Inspection_Form SHALL maintain the existing visual design language with gradient backgrounds and rounded corners
6. THE Inspection_Form SHALL provide visual feedback for all touch interactions with transition animations
