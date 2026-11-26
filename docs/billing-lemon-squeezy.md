# Lemon Squeezy Integration Guide

This document provides an overview of the Lemon Squeezy integration for the SaaS RAG Chatbot application. Lemon Squeezy is used as the payment processor and subscription management platform.

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [API Integration](#api-integration)
4. [Webhook Events](#webhook-events)
5. [Checkout Flow](#checkout-flow)
6. [Subscription Management](#subscription-management)
7. [Usage Tracking](#usage-tracking)
8. [Migration Guide](#migration-guide)

## Overview

Lemon Squeezy is an all-in-one platform for running a SaaS business. It handles:

- Payment processing
- Subscription management
- Tax compliance
- Invoicing
- Customer management
- Checkout experiences

This integration connects our application with Lemon Squeezy to manage subscription plans, process payments, and enforce usage limits based on subscription tiers.

## Configuration

### Environment Variables

The following environment variables need to be set in your `.env` file:

```
LEMONSQUEEZY_API_KEY=your_api_key
LEMONSQUEEZY_STORE_ID=your_store_id
LEMONSQUEEZY_WEBHOOK_SECRET=your_webhook_secret
LEMONSQUEEZY_BASE_URL=https://api.lemonsqueezy.com/v1

# Product and variant IDs for different plans
LEMONSQUEEZY_FREE_VARIANT_ID=variant_id_for_free_plan
LEMONSQUEEZY_PRO_VARIANT_ID=variant_id_for_pro_plan
LEMONSQUEEZY_ENTERPRISE_VARIANT_ID=variant_id_for_enterprise_plan

# Checkout configuration
LEMONSQUEEZY_CHECKOUT_SUCCESS_URL=https://your-app.com/billing/success
LEMONSQUEEZY_CHECKOUT_CANCEL_URL=https://your-app.com/billing/cancel
```

### Lemon Squeezy Dashboard Setup

1. Create a Lemon Squeezy account at [lemonsqueezy.com](https://lemonsqueezy.com)
2. Create a store for your application
3. Create a product with variants for each subscription tier (Free, Pro, Enterprise)
4. Generate an API key in the Settings > API section
5. Set up a webhook in the Settings > Webhooks section with the following URL:
   - `https://your-app.com/api/v1/billing/webhooks/lemonsqueezy`
   - Select all relevant events (subscription_created, subscription_updated, etc.)
   - Generate a signing secret for webhook verification

## API Integration

### Services

The integration consists of the following services:

1. **BillingService** (`app/services/billing_service.py`)
   - Handles API communication with Lemon Squeezy
   - Processes webhook events
   - Manages subscription status updates

2. **CheckoutService** (`app/services/checkout_service.py`)
   - Generates checkout links
   - Manages subscription data

3. **UsageService** (`app/services/usage_service.py`)
   - Tracks resource usage
   - Enforces usage limits based on subscription plans

### API Endpoints

The following API endpoints are available:

- `POST /api/v1/billing/checkout` - Create a checkout session
- `GET /api/v1/billing/subscriptions/{organization_id}` - Get subscription details
- `POST /api/v1/billing/cancel-subscription/{organization_id}` - Cancel a subscription
- `GET /api/v1/billing/plans` - List available subscription plans
- `GET /api/v1/billing/usage/{organization_id}` - Get current usage metrics
- `POST /api/v1/billing/webhooks/lemonsqueezy` - Webhook endpoint for Lemon Squeezy events

## Webhook Events

The application handles the following webhook events from Lemon Squeezy:

- `subscription_created` - When a new subscription is created
- `subscription_updated` - When a subscription is updated (plan change, etc.)
- `subscription_cancelled` - When a subscription is cancelled
- `subscription_resumed` - When a cancelled subscription is resumed
- `subscription_expired` - When a subscription expires
- `order_created` - When a new order is created
- `order_refunded` - When an order is refunded

Each event is processed in the `BillingService.process_webhook_event()` method.

## Checkout Flow

1. User selects a subscription plan in the frontend
2. Frontend calls `POST /api/v1/billing/checkout` with the plan ID and organization ID
3. Backend generates a checkout URL using the Lemon Squeezy API
4. User is redirected to the Lemon Squeezy checkout page
5. After successful payment, Lemon Squeezy sends a webhook event to our application
6. The webhook handler updates the subscription status in our database
7. User is redirected back to our application

## Subscription Management

### Database Models

The subscription data is stored in the following models:

1. **Plan** (`app/db/models/subscription.py`)
   - Represents a subscription plan (Free, Pro, Enterprise)
   - Includes features and limits for each plan

2. **Subscription** (`app/db/models/subscription.py`)
   - Represents an organization's subscription to a plan
   - Links to the Lemon Squeezy subscription

3. **UsageCounter** (`app/db/models/subscription.py`)
   - Tracks resource usage for an organization
   - Used to enforce usage limits

### Subscription Status Flow

```
                  +-------------+
                  |    Trial    |
                  +-------------+
                        |
                        v
+-------------+    +-------------+    +-------------+
|   Pending   | -> |   Active    | -> | Cancelled   |
+-------------+    +-------------+    +-------------+
                        |                   |
                        v                   v
                  +-------------+    +-------------+
                  |  Past Due   | -> |   Expired   |
                  +-------------+    +-------------+
```

## Usage Tracking

The application tracks the following usage metrics:

- **Messages** - Number of messages sent per month
- **Storage** - Amount of storage used (in MB)
- **Bots** - Number of active bots
- **Knowledge Sources** - Number of knowledge sources

Usage limits are enforced based on the subscription plan:

```python
FREE_PLAN_LIMITS = {
    "max_bots": 1,
    "max_messages_per_month": 100,
    "max_storage_mb": 50,
    "max_knowledge_sources": 5
}

PRO_PLAN_LIMITS = {
    "max_bots": 5,
    "max_messages_per_month": 1000,
    "max_storage_mb": 500,
    "max_knowledge_sources": 50
}

ENTERPRISE_PLAN_LIMITS = {
    "max_bots": -1,  # Unlimited
    "max_messages_per_month": -1,
    "max_storage_mb": -1,
    "max_knowledge_sources": -1
}
```

### Usage Middleware

The `UsageLimiterMiddleware` (`app/core/middleware/usage_limiter.py`) provides:

- `check_resource_limit` - Dependency to check if a resource limit has been reached
- `track_usage` - Dependency to track resource usage

Example usage:

```python
@router.post(
    "/bots",
    response_model=BotResponse,
    dependencies=[Depends(check_resource_limit("bots"))]
)
async def create_bot(...):
    # Create bot logic
```

## Migration Guide

To migrate from the previous payment system (or no payment system) to Lemon Squeezy:

1. Run the migration script to add Lemon Squeezy fields to the subscription model:
   ```
   alembic upgrade a1b2c3d4e5f6
   ```

2. Set up the required environment variables in your `.env` file

3. Create products and variants in the Lemon Squeezy dashboard

4. Update existing subscriptions with Lemon Squeezy subscription IDs (if applicable)

5. Test the integration by creating a new subscription and verifying webhook events

## Troubleshooting

### Common Issues

1. **Webhook Verification Fails**
   - Check that the `LEMONSQUEEZY_WEBHOOK_SECRET` environment variable is set correctly
   - Verify that the webhook URL is correct in the Lemon Squeezy dashboard

2. **Checkout Creation Fails**
   - Check that the `LEMONSQUEEZY_API_KEY` and `LEMONSQUEEZY_STORE_ID` are set correctly
   - Verify that the variant IDs are correct

3. **Subscription Status Not Updating**
   - Check the webhook logs for errors
   - Verify that the webhook events are being sent to the correct URL

### Logging

The integration uses structured logging to track events and errors. Check the application logs for entries with the following loggers:

- `app.services.billing_service`
- `app.services.checkout_service`
- `app.services.usage_service`
- `app.core.middleware.usage_limiter`
