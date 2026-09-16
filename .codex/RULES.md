# Multi-Service Platform — Development Rules

These rules are mandatory unless the user explicitly changes them.

---

## 1. Scope Rules

- The approved feature scope is locked.
- Do not add features that are not part of the approved scope.
- Do not remove approved functionality.
- Do not invent business requirements.
- If a requirement is unclear, ask before making a major assumption.
- Current user instructions take priority when they explicitly change an existing requirement.

---

## 2. Service Separation

The platform contains five independent service domains:

- Ride
- Restaurant / Food
- Courier
- Car Rental
- Property / Room

Do not combine all services into one generic service model when their business logic or data is different.

Prefer separate service-specific models.

Examples:

```text
Ride
RideRequest
DriverProfile
DriverVehicle

Restaurant
MenuCategory
FoodItem
FoodOrder
FoodOrderItem

Courier
Delivery
Package

Rental
RentalProvider
RentalVehicle
RentalBooking

Property
PropertyListing
PropertyAvailability
PropertyBooking
```

Shared abstractions are allowed only when the underlying behavior is genuinely common.

---

## 3. Provider Rule

One service provider account can operate **only one service category**.

A provider must not simultaneously act as:

```text
Restaurant + Driver
Restaurant + Courier
Rental + Property
...
```

from the same provider account.

Provider-specific permissions and APIs must respect the provider's service category.

---

## 4. Provider Onboarding

Every service provider has service-specific onboarding information.

The system must track onboarding state.

Conceptually:

```text
Onboarding
    ↓
Submitted
    ↓
Under Review
    ↓
Approved / Rejected
```

A provider must be approved by SuperAdmin before performing normal provider operations.

Do not allow an unapproved provider to:

- Receive service requests
- Manage active service operations
- Accept customer bookings/orders
- Perform other restricted provider actions

unless the requirements explicitly allow it.

---

## 5. Provider Availability

Where a service requires an online/accepting state, the backend must enforce it.

Examples:

```text
Driver:
ONLINE & ACCEPTING

Courier:
ONLINE - ACCEPTING DISPATCH

Restaurant:
ACCEPTING ORDERS

Rental vehicle:
AVAILABLE

Property:
AVAILABLE
```

A frontend toggle alone is not sufficient.

Backend request eligibility must check the appropriate availability state.

---

## 6. Authentication

Use JWT authentication.

Primary actors:

```text
SuperAdmin
Customer
Service Provider
```

Authentication and authorization are separate concerns.

Being authenticated does not automatically mean a user can access every API.

Every protected endpoint must enforce appropriate permissions.

---

## 7. Provider Authorization

Provider endpoints must verify:

1. Authenticated user
2. Provider role
3. Correct service category
4. Required onboarding state
5. Required approval state
6. Relevant ownership of the requested resource

A provider must not be able to access another provider's resources by changing an ID in the request.

Always enforce ownership at the backend.

---

## 8. SuperAdmin Approval

Provider approval is a backend business rule.

SuperAdmin can:

- Review onboarding
- Approve provider
- Reject provider
- Manage users
- Disable user accounts when required
- Manage platform-level administrative information

Approval must not depend only on frontend visibility.

---

## 9. Ownership / Data Isolation

Users should only access resources they are authorized to access.

Examples:

- Customer can access their own bookings/orders.
- Provider can access their own listings.
- Restaurant provider can manage only their own menu.
- Rental provider can manage only their own vehicles.
- Property provider can manage only their own properties.
- Driver can access their own rides.
- Courier can access their assigned/owned deliveries.

Do not rely on frontend filtering for security.

---

## 10. Status Management

Service workflows must use explicit backend status values.

Do not represent important workflow states using arbitrary strings scattered throughout the codebase.

Statuses should be defined centrally within the relevant domain.

Examples:

```text
Ride:
requested
matching
accepted
in_progress
completed
cancelled
```

```text
Food:
placed
confirmed
in_prep
ready
courier_assigned
in_transit
handed_over
cancelled
```

```text
Courier:
requested
assigned
in_transit
delivered
cancelled
```

```text
Rental:
requested
confirmed
completed
cancelled
```

```text
Property:
requested
confirmed
completed
cancelled
```

The exact final status set may be refined during implementation according to the approved workflow.

Invalid status transitions must be rejected by the backend.

---

## 11. State Transitions

Do not allow arbitrary status changes.

For example, a completed ride should not be changed back to `matching`.

Business logic should validate whether a requested transition is allowed.

Status transition rules belong to the relevant service domain.

---

## 12. Payments

Stripe is the payment provider.

Never store raw:

- Card number
- CVC
- Full card details

inside the Django database.

Use Stripe's identifiers/tokens/payment methods according to the appropriate Stripe architecture.

Users may have multiple payment methods.

Payment processing must be separated from general booking/order business logic where practical.

---

## 13. Money

Do not use floating-point numbers for monetary values.

Use appropriate decimal-based money representation.

Currency must be explicit where required.

The platform requirements may use:

```text
BSD
USD
```

Do not silently convert currencies unless the requirement explicitly requires conversion.

---

## 14. Location Data

Location-sensitive services must store the information required by the service.

Where coordinates are required, use appropriate latitude/longitude fields.

Do not store only a human-readable address when the service requires geographic calculations.

Examples:

- Ride pickup/destination
- Courier pickup/drop-off
- Property GPS coordinates
- Rental handover locations

Map API integration must not be hardcoded into unrelated business models.

---

## 15. Real-Time Data

WebSockets should be used for genuinely real-time requirements.

Primary use cases include:

- Ride driver location
- Customer viewing driver location
- Food delivery courier tracking
- Relevant live order/delivery status

Do not use WebSockets for information that can be handled through normal REST APIs.

Redis will support the real-time architecture where required.

---

## 16. Background Jobs

Use Celery for appropriate asynchronous/background operations.

Good candidates include:

- Notifications
- Scheduled tasks
- External API synchronization
- Long-running background processing

Do not unnecessarily move simple CRUD operations into Celery.

---

## 17. API Design

Use Django REST Framework.

Keep APIs organized by domain.

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

Avoid one giant API module.

Service-specific business logic should remain within its domain.

---

## 18. Swagger / OpenAPI

Swagger documentation is mandatory.

Use clear service + actor tags.

Examples:

```text
Rides - Customers
Rides - Provider
Rides - SuperAdmin

Restaurants - Customers
Restaurants - Provider
Restaurants - SuperAdmin

Courier - Customers
Courier - Provider
Courier - SuperAdmin
```

Schemas must expose actual request fields.

Avoid unnecessary generic:

```text
additionalProp
```

representations.

Endpoints should have meaningful descriptions.

---

## 19. Serializers

Serializers should provide:

- Correct field definitions
- Validation
- Clear request/response structures
- Appropriate nested representations
- Useful error messages

Do not put large amounts of complex business logic directly into serializers.

Business rules should have an appropriate service/domain layer when complexity increases.

---

## 20. Models

Models should represent real business concepts.

Do not create extremely generic models simply to reduce the number of files.

Prefer:

```text
Restaurant
FoodItem
FoodOrder
```

over attempting to represent everything as:

```text
Service
Transaction
Item
```

when their behaviors differ.

At the same time, do not duplicate genuinely shared concepts unnecessarily.

---

## 21. Database Integrity

Use database constraints where appropriate.

Examples:

- Unique fields
- Foreign key relationships
- Valid ownership relationships
- Appropriate indexes
- Appropriate nullable/non-nullable fields

Do not rely entirely on frontend validation.

Important business invariants should be enforced at the backend/database level where practical.

---

## 22. File Uploads

Files such as:

- Provider documents
- Licenses
- Vehicle images
- Restaurant images
- Property photos
- Profile photos

must use the project's storage architecture.

Production storage is planned around AWS S3.

Do not store large uploaded files directly inside the database.

---

## 23. Query Efficiency

Avoid obvious N+1 query problems.

Use appropriate:

```text
select_related()
prefetch_related()
```

where necessary.

Do not optimize blindly before understanding the query pattern.

Add database indexes where they support actual filtering/search patterns.

---

## 24. API Filtering

Where requirements specify filtering, filtering must be implemented server-side.

Examples:

- Booking/order status
- Service type
- Completed/cancelled/in-progress
- Provider history
- Date ranges
- Availability

Do not retrieve an unnecessarily large dataset and depend on the frontend to filter it.

---

## 25. Pagination

List endpoints should use appropriate pagination.

Do not return unlimited database records from production APIs.

---

## 26. Error Handling

APIs should return consistent and meaningful errors.

Do not expose:

- Stack traces
- Secrets
- Internal infrastructure details
- Database implementation details

to API consumers.

---

## 27. Security

Never hardcode:

- API keys
- Passwords
- Stripe secrets
- Database credentials
- AWS credentials
- JWT secrets

Use environment-based configuration.

Sensitive configuration must not be committed to Git.

---

## 28. Environment Configuration

Development, staging, and production configuration should be separable.

Use environment variables for environment-specific values.

Do not make production credentials part of source code.

---

## 29. Existing Code Reuse

Existing `users` and `notifications` code from previous projects may be reused.

However:

- Inspect it first.
- Understand it first.
- Adapt it to this project.
- Remove incompatible assumptions.
- Do not blindly copy old architecture.

Existing code is a starting point, not automatically the correct implementation.

---

## 30. Changes to Existing Code

Before modifying an existing component:

1. Understand what currently uses it.
2. Check whether the change affects other domains.
3. Preserve working behavior unless the requirement requires changing it.
4. Avoid unrelated refactoring.

Do not rewrite working modules just for stylistic reasons.

---

## 31. Service Boundaries

Each service domain should own its business logic.

For example:

```text
rides/
    ride logic

restaurants/
    restaurant/order logic

courier/
    delivery logic

rentals/
    rental logic

properties/
    property/booking logic
```

Cross-service communication should be explicit.

Do not create hidden dependencies between unrelated domains.

---

## 32. Testing

New business functionality should have appropriate tests.

Prioritize tests for:

- Authentication
- Permissions
- Provider approval
- Ownership
- Status transitions
- Pricing
- Booking/order creation
- Availability
- Payment-related logic
- Critical service workflows

Do not consider an endpoint complete merely because it returns a successful response.

---

## 33. Migrations

Whenever model changes are made:

- Create migrations.
- Review migrations.
- Apply/test migrations appropriately.

Do not manually modify database structure outside Django migrations unless explicitly required.

---

## 34. Codex Implementation Rule

Codex should work incrementally.

For a requested task:

```text
Understand
    ↓
Inspect existing code
    ↓
Plan
    ↓
Implement
    ↓
Test
    ↓
Review
    ↓
Update progress
```

Do not implement unrelated features just because they appear in the overall project requirements.

---

## 35. No Silent Architecture Changes

Do not make major architectural decisions silently.

Examples of major decisions:

- Changing app boundaries
- Introducing a new abstraction used across domains
- Changing authentication architecture
- Changing payment architecture
- Changing provider/user relationships
- Changing the database strategy
- Introducing a major external service

If such a decision is necessary and not already defined, explain the issue and request confirmation.

---

## 36. Documentation and Progress

After completing a meaningful implementation milestone:

- Update `.codex/PROGRESS.md`.
- Record completed work.
- Record remaining work.
- Record blockers if any.

Do not rewrite the entire progress file unnecessarily.

Keep progress concise and current.