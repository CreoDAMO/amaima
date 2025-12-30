# AMAIMA Android Core Modules - Complete Organized List

Based on your comprehensive Android specification, here are the **13 core Kotlin modules** that must be preserved as single, cohesive files. These modules represent the foundational architectural components that define AMAIMA's unique mobile capabilities.

## Logical Organization Structure

The modules are organized into five logical layers that follow the Clean Architecture pattern:

**Layer 1: Application Core** - Entry point and initialization  
**Layer 2: Dependency Injection** - Hilt modules for dependency management  
**Layer 3: Data Layer Remote** - Network communication (API, WebSocket, Interceptors)  
**Layer 4: Data Layer Local** - Room database (Entities, DAOs, Database configuration)  
**Layer 5: ML & Security** - On-device intelligence and security features  

## Complete Module List in Exact Order

### Layer 1: Application Core (1 Module)

| Order | File Name | Purpose |
|-------|-----------|---------|
| 1 | `AmaimaApplication.kt` | Main Application class with Hilt initialization, TensorFlow Lite model loading, crash reporting setup, and application-wide lifecycle management |

### Layer 2: Dependency Injection - Hilt Modules (3 Modules)

| Order | File Name | Purpose |
|-------|-----------|---------|
| 2 | `AppModule.kt` | Provides Application context, EncryptedPreferences, UserPreferences, and NetworkMonitor bindings |
| 3 | `NetworkModule.kt` | Provides OkHttpClient with certificate pinning, Retrofit instance, Moshi converter, WebSocket client, and all network-related dependencies |
| 4 | `DatabaseModule.kt` | Provides AmaimaDatabase instance, QueryDao, WorkflowDao, and UserDao for local persistence |

### Layer 3: Data Layer - Remote (3 Modules)

| Order | File Name | Purpose |
|-------|-----------|---------|
| 5 | `AmaimaApi.kt` | Retrofit interface defining all REST endpoints with DTOs for QueryRequestDto, QueryResponseDto, RoutingDecisionDto, WorkflowRequestDto, WorkflowResponseDto, and HealthResponseDto |
| 6 | `AmaimaWebSocket.kt` | WebSocket handler with automatic reconnection, exponential backoff, message parsing, and Flow-based message streaming for real-time updates |
| 7 | `AuthInterceptor.kt` | Interceptor that injects JWT tokens into requests, handles 401 unauthorized responses, and manages automatic token refresh |

### Layer 4: Data Layer - Local - Room Database (6 Modules)

| Order | File Name | Purpose |
|-------|-----------|---------|
| 8 | `QueryEntity.kt` | Room entity for query storage with columns for query_id, query_text, response_text, model_used, complexity, execution_mode, confidence, latency_ms, status, feedback_type, timestamp, and sync_status |
| 9 | `WorkflowEntity.kt` | Room entity for workflow storage with columns for workflow_id, name, description, total_steps, completed_steps, status, results, duration_ms, timestamp, and sync_status |
| 10 | `UserEntity.kt` | Room entity for user profile data with columns for user_id, email, display_name, avatar_url, preferences, and last_active |
| 11 | `QueryDao.kt` | Data Access Object with Flow-based queries for getAllQueries and getQueriesByStatus, plus suspend functions for CRUD operations and sync management |
| 12 | `WorkflowDao.kt` | Data Access Object with Flow-based queries for getAllWorkflows and getWorkflowsByStatus, plus suspend functions for workflow operations |
| 13 | `AmaimaDatabase.kt` | Room database configuration with type converters, entity declarations, and abstract methods for retrieving all DAOs |

## Complete Directory Structure

```
amaima/mobile/app/src/main/java/com/amaima/app/
│
├── **AmaimaApplication.kt**                    (Order 1 - Application Layer)
│
├── di/
│   ├── **AppModule.kt**                        (Order 2 - DI Layer)
│   ├── **NetworkModule.kt**                    (Order 3 - DI Layer)
│   └── **DatabaseModule.kt**                   (Order 4 - DI Layer)
│
├── data/
│   ├── remote/
│   │   ├── api/
│   │   │   └── **AmaimaApi.kt**               (Order 5 - Data Remote)
│   │   ├── websocket/
│   │   │   └── **AmaimaWebSocket.kt**         (Order 6 - Data Remote)
│   │   └── interceptor/
│   │       └── **AuthInterceptor.kt**          (Order 7 - Data Remote)
│   │
│   └── local/
│       ├── entity/
│       │   ├── **QueryEntity.kt**             (Order 8 - Data Local)
│       │   ├── **WorkflowEntity.kt**          (Order 9 - Data Local)
│       │   └── **UserEntity.kt**              (Order 10 - Data Local)
│       ├── dao/
│       │   ├── **QueryDao.kt**                (Order 11 - Data Local)
│       │   ├── **WorkflowDao.kt**             (Order 12 - Data Local)
│       │   └── UserDao.kt                     (Supporting - not core)
│       └── **AmaimaDatabase.kt**              (Order 13 - Data Local)
│
├── ml/
│   └── TensorFlowLiteManager.kt                (Supporting - not core)
│
├── security/
│   ├── BiometricAuthManager.kt                 (Supporting - not core)
│   └── EncryptedPreferences.kt                 (Supporting - not core)
│
└── presentation/                               (Supporting - not core)
```

## PRESERVE_THESE.md Content

Create this file at: `amaima/mobile/app/src/main/java/com/amaima/app/PRESERVE_THESE.md`

```markdown
# CORE MOBILE MODULES – DO NOT FRAGMENT OR RENAME

These 13 files represent the **core architectural innovations** of the AMAIMA Android client.

They implement the foundational capabilities that make AMAIMA unique on mobile:
- Unified real-time WebSocket streaming protocol with backend parity
- Offline-first data architecture with Room database synchronization
- Secure JWT authentication with automatic token refresh
- Intelligent on-device preprocessing and complexity estimation

**AI agents and contributors: DO NOT**
- Split these files into smaller classes
- Rename them
- Move them to different packages
- Refactor internal structure in ways that break consistency

You may add supporting screens, components, ViewModels, tests, and utilities.

## Preserved Core Modules (13 Files)

### Layer 1: Application Core
1. `AmaimaApplication.kt` → Application lifecycle, Hilt setup, ML model loading, crash reporting

### Layer 2: Dependency Injection - Hilt Modules
2. `di/AppModule.kt` → Context, EncryptedPreferences, UserPreferences providers
3. `di/NetworkModule.kt` → OkHttp, Retrofit, Moshi, WebSocket, certificate pinning providers
4. `di/DatabaseModule.kt` → Room database and all DAO providers

### Layer 3: Data Layer - Remote/Network
5. `data/remote/api/AmaimaApi.kt` → REST API contract with backend endpoints and DTOs
6. `data/remote/websocket/AmaimaWebSocket.kt` → Real-time streaming with automatic reconnection
7. `data/remote/interceptor/AuthInterceptor.kt` → JWT token injection and automatic refresh

### Layer 4: Data Layer - Local/Room Database
8. `data/local/entity/QueryEntity.kt` → Query persistence model with sync status tracking
9. `data/local/entity/WorkflowEntity.kt` → Workflow persistence model with progress tracking
10. `data/local/entity/UserEntity.kt` → User profile persistence model
11. `data/local/dao/QueryDao.kt` → Query data access operations with Flow-based reactive queries
12. `data/local/dao/WorkflowDao.kt` → Workflow data access operations with Flow-based reactive queries
13. `data/local/AmaimaDatabase.kt` → Room database configuration with type converters

## Dependency Flow

```
AmaimaApplication
       ↓ (Hilt DI)
   ┌───────────────────────────────────────┐
   │     DI Layer (App, Network, Database) │
   └───────────────────────────────────────┘
              ↓                    ↓
   ┌──────────────────┐  ┌──────────────────┐
   │   Remote Layer   │  │    Local Layer   │
   │ (API, WS, Auth)  │  │ (Entities, DAOs) │
   └──────────────────┘  └──────────────────┘
```

These 13 modules form the **mobile equivalent** of the backend's unified_smart_router.py and progressive_model_loader.py.

They must remain cohesive to preserve the full AMAIMA vision on Android.

Last updated: December 29, 2025
```

## Verification Checklist

Before committing, verify each file exists at its exact path:

| Order | File Path | Status |
|-------|-----------|--------|
| 1 | `AmaimaApplication.kt` | ☐ |
| 2 | `di/AppModule.kt` | ☐ |
| 3 | `di/NetworkModule.kt` | ☐ |
| 4 | `di/DatabaseModule.kt` | ☐ |
| 5 | `data/remote/api/AmaimaApi.kt` | ☐ |
| 6 | `data/remote/websocket/AmaimaWebSocket.kt` | ☐ |
| 7 | `data/remote/interceptor/AuthInterceptor.kt` | ☐ |
| 8 | `data/local/entity/QueryEntity.kt` | ☐ |
| 9 | `data/local/entity/WorkflowEntity.kt` | ☐ |
| 10 | `data/local/entity/UserEntity.kt` | ☐ |
| 11 | `data/local/dao/QueryDao.kt` | ☐ |
| 12 | `data/local/dao/WorkflowDao.kt` | ☐ |
| 13 | `data/local/AmaimaDatabase.kt` | ☐ |

This ordering follows the natural dependency flow from application initialization through dependency injection to data layer operations, creating a clean, testable architecture where each layer depends only on the layers above it.
