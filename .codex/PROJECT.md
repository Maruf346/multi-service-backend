# Multi-Service Platform — Project Context

## 1. Project Overview

This is a multi-service booking and delivery platform supporting:

1. Ride Sharing
2. Food Delivery
3. Courier Delivery
4. Car Rental
5. Room / Property Booking

The platform consists of:

- Flutter mobile application for customers and service providers
- React-based SuperAdmin dashboard
- Django + Django REST Framework backend
- PostgreSQL database
- Redis
- Celery
- WebSockets for required real-time functionality
- Stripe for payments
- AWS infrastructure
- Dockerized deployment

The project scope is based on the locked feature requirements.

Do not introduce features outside the approved scope unless explicitly requested.

---

# 2. Backend Project Structure

The Django project uses a `core` project for configuration and an `apps` directory for Django applications.

Expected high-level structure:

```text
project-root/
│
├── core/
│   ├── settings/
│   ├── urls.py
│   ├── asgi.py
│   └── ...
│
├── apps/
│   ├── users/
│   ├── notifications/
│   ├── api/
│   │   ├── a tunnel to connect all the apis from each of the apps urls.py
│   │
│   └── ...
│
├── .codex/
│   ├── PROJECT.md
│   ├── RULES.md
│   └── PROGRESS.md
│
├── manage.py
└── ...
```

The exact structure may be adjusted during implementation if a better separation is identified.

The important principle is that service-specific functionality must remain separated.

---

# 3. Application Responsibilities

## 3.1 `users`

Responsible for platform-level user identity and authentication.

Main responsibilities:

- Custom user model
- Registration
- Login
- JWT authentication
- User profile
- Phone information
- Profile image
- Address/location information
- Account status / activation
- User-level payment method relationships
- User role information

The existing users application from the previous project may be reused as a starting point, but it must be adapted to this project.

Do not blindly copy previous implementation.

---

## 3.2 `notifications`

Responsible for platform notifications.

Responsibilities include:

- Notification model
- Notification creation
- Notification retrieval
- Read/unread state
- Service-related notifications
- Booking/order status notifications
- Provider/customer notifications

An existing notification implementation from a previous project will be adapted.

---

# 4. API Application Structure

Service APIs should live under:

```text
apps/api/
```

Each major service should have its own domain separation.

Recommended structure:

```text
apps/api/
├── common/
├── rides/
├── restaurants/
├── courier/
├── rentals/
└── properties/
```

Each service should contain its own relevant:

- Models
- Serializers
- Views / ViewSets
- URLs
- Filters
- Permissions
- Services / business logic
- Tests

Avoid creating one giant `services` model or one giant API module containing all service types.

---

# 5. Shared vs Service-Specific Design

The platform has some shared concepts:

- Users
- Providers
- Notifications
- Favorites
- Ratings / Reviews
- Payment methods
- Locations
- Files / media
- Authentication

However, the five service domains have substantially different data and workflows.

Therefore:

### Shared functionality

Should be abstracted only when the underlying concept and behavior are genuinely shared.

### Service-specific functionality

Should have separate models and business logic.

For example:

```text
Ride
Restaurant
FoodItem
FoodOrder
CourierDelivery
RentalVehicle
RentalBooking
Property
PropertyBooking
```

should not be forced into one generic transaction/service model.

---

# 6. User and Provider Model Concept

There are three primary platform actors:

```text
SuperAdmin
Normal User
Service Provider
```

A service provider operates exactly one service category.

Provider categories:

```text
Ride
Restaurant / Food
Courier
Car Rental
Property
```

Provider onboarding is service-specific because every service requires different information and documents.

Provider onboarding must track at least:

```text
onboarding status
approval status
service category
```

The provider must be approved by SuperAdmin before performing normal provider operations.

---

# 7. Common Platform Concepts

## 7.1 Favorites

Users can favorite service-specific entities.

Examples:

- Ride-related providers
- Restaurants
- Vehicles
- Properties

The implementation should allow retrieving favorites by relevant service.

Do not duplicate unrelated favorite systems unnecessarily.

---

## 7.2 Ratings and Reviews

Ratings are optional after applicable completed services.

Common rating information:

- Rating out of 5
- Notes
- Multiple selectable highlights / tags

The selectable highlight values may differ depending on service context.

Examples from the approved requirements include:

```text
Smooth Driving
Punctual & Professional
```

Food item ratings may be associated with individual food items when an order contains multiple items.

---

## 7.3 Locations

Location data is important throughout the platform.

Depending on the service, location information may include:

- Address
- Latitude
- Longitude
- Pickup location
- Destination
- Drop-off location
- Operational zone
- Property location
- Rental handover location

Location data should be modeled consistently where possible while allowing service-specific requirements.

---

# 8. Ride Module

Location:

```text
apps/api/rides/
```

## Main concepts

The Ride module should contain separate concepts for:

- Ride provider / driver profile
- Driver documents
- Vehicle information
- Ride request
- Ride status
- Ride location/tracking data where required
- Ride payment information
- Ride rating/review relationship

## Customer flow

```text
Select pickup
      ↓
Select destination
      ↓
Calculate distance / estimated duration
      ↓
Select payment method
      ↓
Select passenger capacity
      ↓
Calculate/display fare
      ↓
Request ride
      ↓
Matching
      ↓
Driver accepts
      ↓
Live driver tracking
      ↓
Ride starts
      ↓
Ride completes
      ↓
Payment
      ↓
Optional tip
      ↓
Optional rating/review
```

## Driver flow

```text
Complete onboarding
      ↓
SuperAdmin approval
      ↓
Set online / accepting
      ↓
Receive ride request
      ↓
Accept / reject
      ↓
Navigate to customer
      ↓
Live location updates
      ↓
Complete ride
      ↓
Ride history / earnings
```

## Important ride data

Customer ride requests require:

- Pickup location
- Destination
- Distance
- Estimated duration
- Passenger capacity
- Payment method
- Fare
- Ride status

Driver information includes:

- Legal name
- Contact information
- Driver license
- Regulatory documents
- Vehicle category
- Vehicle information
- Seat capacity
- VIN
- Online / accepting status
- Onboarding / approval status

---

# 9. Restaurant / Food Module

Location:

```text
apps/api/restaurants/
```

## Main concepts

Separate models should be considered for:

- Restaurant provider
- Restaurant onboarding information
- Restaurant operating hours / availability
- Menu category
- Food item
- Food item media
- Food order
- Order item
- Courier assignment
- Order status
- Food rating/review

## Customer flow

```text
Browse restaurants
      ↓
Select restaurant
      ↓
Browse categories/items
      ↓
Add items to cart
      ↓
Checkout
      ↓
Select delivery location
      ↓
Payment / Cash on Delivery
      ↓
Order placed
      ↓
Restaurant confirmation
      ↓
Preparation
      ↓
Courier assigned
      ↓
In transit + live tracking
      ↓
Handover
      ↓
Optional ratings/reviews
```

## Restaurant provider flow

```text
Complete onboarding
      ↓
SuperAdmin approval
      ↓
Manage restaurant profile
      ↓
Manage categories
      ↓
Manage menu items
      ↓
Receive orders
      ↓
Accept order
      ↓
Prepare order
      ↓
Hand over to courier
      ↓
View order history/statistics
```

Food items must support:

- Name
- Description
- Price
- Photo
- Preparation window
- Dietary/kitchen tags
- Availability

---

# 10. Courier Module

Location:

```text
apps/api/courier/
```

## Main concepts

Separate models should cover:

- Courier provider
- Courier onboarding
- Courier documents
- Delivery request
- Package information
- Delivery assignment
- Delivery status
- Delivery tracking
- Delivery history
- Earnings
- Rating/review

## Customer flow

```text
Select courier
      ↓
Pickup information
      ↓
Recipient information
      ↓
Delivery instructions
      ↓
Package details
      ↓
Calculate delivery cost
      ↓
Payment
      ↓
Delivery booked
      ↓
Courier assigned
      ↓
Pickup
      ↓
In transit
      ↓
Delivered
      ↓
Optional rating/review
```

Package information includes:

- Size category
- Package contents description
- Fragile/high-value flag
- Transit insurance where applicable

The pickup handover process uses a 4-digit PIN.

## Courier provider flow

```text
Complete onboarding
      ↓
SuperAdmin approval
      ↓
Set online / accepting dispatch
      ↓
Receive delivery request
      ↓
Accept
      ↓
Pickup
      ↓
In transit
      ↓
Delivered
      ↓
View history / earnings / ratings
```

---

# 11. Car Rental Module

Location:

```text
apps/api/rentals/
```

## Main concepts

A rental provider can own/manage multiple vehicles.

Separate models should cover:

- Rental provider
- Rental provider onboarding
- Vehicle
- Vehicle photos/media
- Vehicle availability
- Rental booking
- Rental pricing/security information
- Rental booking status
- Rental history
- Rating/review

Relationship concept:

```text
Rental Provider
      │
      ├── Vehicle
      ├── Vehicle
      ├── Vehicle
      └── ...
```

A customer selects a provider, browses its vehicles, and books a specific vehicle.

## Customer flow

```text
Browse providers
      ↓
Browse vehicles
      ↓
Select vehicle
      ↓
Select pickup/handover location
      ↓
Select rental dates
      ↓
Select handover time
      ↓
Optional villa/hotel delivery
      ↓
Calculate rental + VAT + refundable security
      ↓
Payment
      ↓
Booking request
      ↓
Provider confirmation
      ↓
Rental completion
      ↓
Optional rating/review
```

Vehicle data includes:

- Photos
- Make
- Model
- Year
- Category/class
- License plate
- RTD livery tag
- Engine/powertrain
- Seating
- Luggage capacity
- Transmission
- Fuel tank
- Daily rate
- Security escrow deposit
- Minimum rental period
- Availability
- Authorized staging/handover zones

---

# 12. Property / Room Module

Location:

```text
apps/api/properties/
```

## Main concepts

Separate models should cover:

- Property owner/provider
- Property onboarding
- Property/listing
- Property photos
- Amenities
- Availability
- Property booking
- Booking status
- Rating/review

Relationship:

```text
Property Provider
      │
      ├── Property / Listing
      ├── Property / Listing
      └── ...
```

## Customer flow

```text
Browse providers
      ↓
Browse properties
      ↓
Select property
      ↓
Select booking dates
      ↓
Select number of persons
      ↓
Enter primary guest information
      ↓
Calculate total
      ↓
Payment
      ↓
Booking
      ↓
Completion
      ↓
Optional rating/review
```

Property listing information includes:

- Photos
- Property title
- Description
- Bedrooms
- Bathrooms
- Maximum guests
- Island / Cay region
- Street address
- GPS coordinates
- Nightly rate
- Minimum stay
- Cleaning fee
- Security/damage deposit
- Amenities

Availability must support date-based checking.

---

# 13. SuperAdmin Module

SuperAdmin functionality may be organized under the relevant service APIs where appropriate, while maintaining clear permission boundaries.

SuperAdmin responsibilities include:

## Provider approval

```text
Provider submits onboarding
        ↓
SuperAdmin receives request
        ↓
Review information/documents
        ↓
Approve / Decline
```

A provider cannot perform normal service operations before approval.

## User management

SuperAdmin can:

- View users
- View user details
- Manage account activation
- Disable accounts when required for security
- Manage SuperAdmin profile
- Change password

## Provider management

SuperAdmin can review providers by service category:

```text
Ride
Restaurant
Courier
Car Rental
Property
```

---

# 14. API Design

All backend functionality should be exposed through Django REST Framework APIs.

API URLs should remain organized by domain.

Conceptually:

```text
/api/
    auth/
    users/
    notifications/

    rides/
    restaurants/
    courier/
    rentals/
    properties/
```

The exact URL structure can be finalized during API implementation.

---

# 15. Swagger / OpenAPI

Swagger documentation is required for the backend.

Tags should identify both service and actor.

Examples:

```text
Restaurants - Provider
Restaurants - Customers
Restaurants - SuperAdmin

Rides - Provider
Rides - Customers
Rides - SuperAdmin

Courier - Provider
Courier - Customers
Courier - SuperAdmin

Rentals - Provider
Rentals - Customers
Rentals - SuperAdmin

Properties - Provider
Properties - Customers
Properties - SuperAdmin
```

Schemas should expose actual fields and should not produce unnecessary generic `additionalProp` fields.

Every endpoint should have useful descriptions and accurate request/response schemas.

---

# 16. Authentication and Authorization

JWT authentication is used.

Authorization must distinguish:

```text
SuperAdmin
Customer
Service Provider
```

Provider authorization must additionally verify the provider's service category.

Provider endpoints must verify relevant onboarding/approval state where required.

Provider-specific endpoints must not allow a provider from one service category to access another service's provider functionality.

---

# 17. Payments

Stripe is the payment provider.

The system needs payment functionality for applicable services and payment-method management.

Customers can have multiple payment methods.

Providers also require payment-related functionality for receiving payments.

Payment implementation must follow Stripe's proper architecture.

Raw card information must not be stored in the Django database.

The exact Stripe integration architecture will be defined before implementation of payment functionality.

---

# 18. Real-Time Features

WebSockets are required where the approved requirements call for live updates.

Primary real-time use cases include:

### Ride

- Driver live location
- Customer viewing driver location
- Ride state updates

### Food Delivery

- Delivery person's live location
- Order milestone/status updates

### Courier

- Delivery status
- Location tracking where required

Django ASGI/Daphne and Redis will be used as part of the real-time architecture.

Celery should be used for asynchronous/background work where appropriate rather than blocking API requests.

---

# 19. Background Processing

Celery + Redis will handle appropriate asynchronous operations.

Potential use cases include:

- Notifications
- Background processing
- Scheduled tasks
- External API synchronization
- Other operations that should not block HTTP requests

Do not introduce Celery for simple synchronous operations without a reason.

---

# 20. External Services

The platform may integrate with:

### Maps / Location

A map/location provider will be used for:

- Coordinates
- Distance calculation
- Estimated duration
- Map-related functionality
- Live location display

The exact provider/API should be confirmed before implementation.

### Stripe

Used for payment processing and payment methods.

### AWS

Planned infrastructure:

```text
EC2
S3
ECR
PostgreSQL
Docker
```

The backend should be prepared for Dockerized deployment.

---

# 21. Implementation Strategy

Implementation should proceed incrementally.

## Phase 1 — Foundation

- Django project configuration
- Environment configuration
- PostgreSQL setup
- Custom user system
- JWT authentication
- Base permissions
- Base API structure
- Existing notification system adaptation

## Phase 2 — Shared Platform

- User profile
- Provider identity/structure
- Favorites
- Ratings/reviews foundation
- Payment-method foundation
- File/media handling
- Common location structures

## Phase 3 — Ride

- Provider onboarding
- Driver/vehicle models
- Admin approval
- Ride request
- Matching
- Fare calculation
- Ride lifecycle
- Tracking
- History
- Rating

## Phase 4 — Restaurant / Food

- Restaurant onboarding
- Admin approval
- Categories
- Menu
- Food items
- Cart/order
- Order lifecycle
- Courier assignment
- Tracking
- Ratings

## Phase 5 — Courier

- Courier onboarding
- Admin approval
- Delivery request
- Package information
- Assignment
- Delivery lifecycle
- Tracking
- PIN
- History
- Ratings

## Phase 6 — Car Rental

- Rental provider onboarding
- Admin approval
- Vehicle CRUD
- Vehicle availability
- Rental booking
- Pricing/security deposit
- Booking lifecycle
- History
- Ratings

## Phase 7 — Property

- Property owner onboarding
- Admin approval
- Property CRUD
- Photos/media
- Amenities
- Availability
- Booking
- Booking lifecycle
- History
- Ratings

## Phase 8 — Payments / Real-Time / Notifications

Complete and integrate:

- Stripe payment flows
- Payment methods
- Provider payments
- WebSockets
- Redis
- Celery
- Notifications
- Service-specific events

## Phase 9 — API Quality

- Swagger/OpenAPI
- Permissions review
- Validation
- Error handling
- Filtering
- Pagination
- API consistency
- Tests

## Phase 10 — Deployment

- Docker
- Production configuration
- PostgreSQL
- Redis
- Celery workers
- ASGI/Daphne
- S3
- EC2
- ECR
- Production security configuration

---

# 22. Development Approach

Build one domain at a time.

Do not attempt to implement the entire platform in one step.

For every feature:

```text
Requirements
    ↓
Models
    ↓
Migrations
    ↓
Serializers
    ↓
Business logic
    ↓
Views / ViewSets
    ↓
URLs
    ↓
Permissions
    ↓
Swagger
    ↓
Tests
    ↓
Progress update
```

Before implementing a new domain, inspect existing shared functionality and reuse it only when the behavior genuinely matches.

Avoid unnecessary duplication, but also avoid premature abstraction.

---

# 23. Codex Working Instructions

Before making changes, Codex should:

1. Read this file.
2. Read `.codex/RULES.md`.
3. Read `.codex/PROGRESS.md`.
4. Inspect the current codebase.
5. Identify the relevant app/domain.
6. Check existing implementations before creating duplicates.
7. Implement only the requested task.
8. Avoid unrelated refactoring.
9. Run relevant checks/tests after implementation.
10. Report what was changed.
11. Identify any remaining work.
12. Update `.codex/PROGRESS.md` when a meaningful task is completed.

If the requirements and existing implementation conflict, do not silently change the requirements.

If an architectural decision is required and is not already documented, stop and ask before making a major structural decision.

---

# 24. Current Starting Point

The Django project has already been created.

Current structure includes:

```text
core/
apps/
```

The `apps` directory is the location for Django applications.

The API functionality will be organized under:

```text
apps/api/
```

The existing `users` and `notifications` applications from a previous project are intended to be added/adapted.

The project is currently at the foundation/setup stage.

Refer to:

```text
.codex/PROGRESS.md
```

for the current implementation state.

---

# 25. Important Principle

This project is a collection of independent service domains sharing a common platform foundation.

The architecture should therefore look conceptually like:

```text
                    Platform
                       │
          ┌────────────┼────────────┐
          │            │            │
        Users      Notifications   Payments
          │
          │
     ┌────┴──────────────────────────────────┐
     │                                       │
     │          Service Domains              │
     │                                       │
     ├── Ride                                 │
     ├── Restaurant / Food                    │
     ├── Courier                              │
     ├── Car Rental                           │
     └── Property                             │
                                             │
     └───────────────────────────────────────┘
```

Each domain should remain independently understandable and maintainable.

Shared infrastructure should support the domains without forcing their business logic into one generic implementation.