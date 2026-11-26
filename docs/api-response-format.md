## Standardized API Response Format

All API endpoints now follow a consistent response format for both success and error cases.

## Response Structure

### Success Response

```typescript
{
  success: boolean;      // Always true for successful responses
  data: T | null;        // Response data (type varies by endpoint)
  message?: string;      // Optional success message
  status_code: number;   // HTTP status code
}
```

### Error Response

```typescript
{
  success: boolean;      // Always false for error responses
  error: string;         // Error code (e.g., "VALIDATION_ERROR", "NOT_FOUND")
  message: string;       // Human-readable error message
  details?: any;         // Optional additional error details
  status_code: number;   // HTTP status code
}
```

---

## Success Response Examples

### 1. Registration (201 Created)

**Request:**
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123",
  "full_name": "John Doe",
  "organization_name": "Acme Corp"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "full_name": "John Doe",
      "is_active": true,
      "is_verified": false,
      "is_superadmin": false,
      "last_login": null,
      "created_at": "2024-10-15T10:30:00Z"
    },
    "organization": {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "name": "Acme Corp",
      "slug": "acme-corp"
    }
  },
  "message": "Registration successful. Please check your email to verify your account.",
  "status_code": 201
}
```

### 2. Login (200 OK)

**Request:**
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "full_name": "John Doe",
      "is_active": true,
      "is_verified": true,
      "is_superadmin": false,
      "last_login": "2024-10-15T10:35:00Z",
      "created_at": "2024-10-15T10:30:00Z"
    },
    "tokens": {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 10800
    }
  },
  "message": "Login successful",
  "status_code": 200
}
```

### 3. Get Current User (200 OK)

**Request:**
```http
GET /api/v1/auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response:**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "full_name": "John Doe",
      "is_active": true,
      "is_verified": true,
      "is_superadmin": false,
      "last_login": "2024-10-15T10:35:00Z",
      "created_at": "2024-10-15T10:30:00Z"
    }
  },
  "message": "User profile retrieved successfully",
  "status_code": 200
}
```

### 4. Message-Only Response (200 OK)

**Request:**
```http
POST /api/v1/auth/forgot-password
Content-Type: application/json

{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "If the email exists, a password reset link has been sent.",
  "status_code": 200
}
```

---

## Error Response Examples

### 1. Validation Error (422 Unprocessable Entity)

**Request:**
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "invalid-email",
  "password": "123"
}
```

**Response:**
```json
{
  "success": false,
  "error": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "input": "invalid-email"
    },
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 6 characters",
      "input": "123"
    }
  ],
  "status_code": 422
}
```

### 2. Email Already Exists (400 Bad Request)

**Request:**
```http
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "existing@example.com",
  "password": "SecurePass123",
  "full_name": "Jane Doe"
}
```

**Response:**
```json
{
  "success": false,
  "error": "EMAIL_EXISTS",
  "message": "Email already registered",
  "status_code": 400
}
```

### 3. Invalid Credentials (401 Unauthorized)

**Request:**
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "WrongPassword"
}
```

**Response:**
```json
{
  "success": false,
  "error": "INVALID_CREDENTIALS",
  "message": "Invalid email or password",
  "status_code": 401
}
```

### 4. Unauthorized Access (401 Unauthorized)

**Request:**
```http
GET /api/v1/auth/me
```

**Response:**
```json
{
  "success": false,
  "error": "UNAUTHORIZED",
  "message": "Not authenticated",
  "status_code": 401
}
```

### 5. Forbidden (403 Forbidden)

**Request:**
```http
GET /api/v1/admin/users
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response:**
```json
{
  "success": false,
  "error": "FORBIDDEN",
  "message": "Permission denied",
  "status_code": 403
}
```

### 6. Not Found (404 Not Found)

**Request:**
```http
GET /api/v1/bots/999
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Response:**
```json
{
  "success": false,
  "error": "NOT_FOUND",
  "message": "Bot not found",
  "status_code": 404
}
```

### 7. Rate Limit Exceeded (429 Too Many Requests)

**Request:**
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Response:**
```json
{
  "success": false,
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Please try again later.",
  "status_code": 429
}
```

### 8. Internal Server Error (500 Internal Server Error)

**Response:**
```json
{
  "success": false,
  "error": "INTERNAL_SERVER_ERROR",
  "message": "An internal error occurred",
  "status_code": 500
}
```

---

## Error Codes Reference

| Error Code | Status Code | Description |
|-----------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Request validation failed |
| `EMAIL_EXISTS` | 400 | Email already registered |
| `INVALID_CREDENTIALS` | 401 | Invalid email or password |
| `UNAUTHORIZED` | 401 | Not authenticated |
| `INVALID_TOKEN` | 401 | Invalid or expired token |
| `EMAIL_NOT_VERIFIED` | 403 | Email not verified |
| `FORBIDDEN` | 403 | Permission denied |
| `INACTIVE_ACCOUNT` | 403 | Account is inactive |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_SERVER_ERROR` | 500 | Internal error |

---

## Using in Frontend

### TypeScript Interface

```typescript
// Base response type
interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
  details?: any;
  status_code: number;
}

// Success response
interface SuccessResponse<T> {
  success: true;
  data: T;
  message?: string;
  status_code: number;
}

// Error response
interface ErrorResponse {
  success: false;
  error: string;
  message: string;
  details?: any;
  status_code: number;
}
```

### Example Usage (React/TypeScript)

```typescript
import axios from 'axios';

// Login function
async function login(email: string, password: string) {
  try {
    const response = await axios.post<ApiResponse>('/api/v1/auth/login', {
      email,
      password
    });
    
    if (response.data.success) {
      // Handle success
      const { user, tokens } = response.data.data;
      localStorage.setItem('access_token', tokens.access_token);
      console.log('Logged in:', user.email);
      return { success: true, user };
    }
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      const errorData = error.response.data as ErrorResponse;
      
      // Handle specific errors
      if (errorData.error === 'INVALID_CREDENTIALS') {
        return { success: false, error: 'Invalid email or password' };
      }
      
      return { success: false, error: errorData.message };
    }
    
    return { success: false, error: 'Network error' };
  }
}

// Register function
async function register(data: RegisterData) {
  try {
    const response = await axios.post<ApiResponse>('/api/v1/auth/register', data);
    
    if (response.data.success) {
      return {
        success: true,
        message: response.data.message,
        user: response.data.data.user
      };
    }
  } catch (error) {
    if (axios.isAxiosError(error) && error.response) {
      const errorData = error.response.data as ErrorResponse;
      
      // Handle validation errors
      if (errorData.error === 'VALIDATION_ERROR' && errorData.details) {
        const validationErrors = errorData.details.reduce((acc, err) => {
          const field = err.loc[err.loc.length - 1];
          acc[field] = err.msg;
          return acc;
        }, {});
        
        return { success: false, validationErrors };
      }
      
      return { success: false, error: errorData.message };
    }
    
    return { success: false, error: 'Network error' };
  }
}
```

### Axios Interceptor Example

```typescript
import axios from 'axios';

// Add response interceptor for consistent error handling
axios.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const errorData = error.response.data as ErrorResponse;
      
      // Handle specific error codes globally
      if (errorData.error === 'UNAUTHORIZED') {
        // Redirect to login
        window.location.href = '/login';
      }
      
      if (errorData.error === 'RATE_LIMIT_EXCEEDED') {
        // Show rate limit message
        alert('Too many requests. Please try again later.');
      }
    }
    
    return Promise.reject(error);
  }
);
```

---

## Benefits of Standardized Responses

✅ **Consistency**: All endpoints follow the same structure  
✅ **Type Safety**: Easy to create TypeScript interfaces  
✅ **Error Handling**: Predictable error format with error codes  
✅ **Client-Side**: Simplified response parsing  
✅ **Documentation**: Clear and consistent API documentation  
✅ **Debugging**: Easy to identify response type (success/error)  
✅ **Future-Proof**: Easy to add new fields without breaking changes  

---

## Migration Notes

All authentication endpoints have been updated to use this format. Future endpoints should follow this pattern using the helper functions in `app/utils/response.py`:

```python
from app.utils.response import success_response, created_response, message_response

# For successful responses with data
return success_response(
    data={"user": user_data},
    message="Operation successful"
)

# For created resources (201)
return created_response(
    data={"resource": resource_data},
    message="Resource created"
)

# For message-only responses
return message_response(
    message="Operation completed successfully"
)
```

Error responses are automatically handled by the exception handlers in `app/main.py`.

