@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    state: HomeState,
    onQueryClick: () -> Unit,
    onWorkflowClick: () -> Unit,
    onQueryHistoryItemClick: (String) -> Unit,
    onSettingsClick: () -> Unit,
    isOnline: Boolean
) {
    val context = LocalContext.current

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "AMAIMA",
                            style = MaterialTheme.typography.headlineMedium
                        )
                        Text(
                            text = if (isOnline) "Connected" else "Offline Mode",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (isOnline) {
                                MaterialTheme.colorScheme.primary
                            } else {
                                MaterialTheme.colorScheme.error
                            }
                        )
                    }
                },
                actions = {
                    IconButton(onClick = { /* Notifications */ }) {
                        BadgedBox(
                            badge = {
                                if (state.pendingFeedbackCount > 0) {
                                    Badge { Text(state.pendingFeedbackCount.toString()) }
                                }
                            }
                        ) {
                            Icon(Icons.Default.Notifications, contentDescription = "Notifications")
                        }
                    }
                    IconButton(onClick = onSettingsClick) {
                        Icon(Icons.Default.Settings, contentDescription = "Settings")
                    }
                }
            )
        }
    ) { paddingValues ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
                .pullToRefresh(
                    isRefreshing = state.isRefreshing,
                    onRefresh = { /* Handle refresh */ }
                ),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                SystemStatusCard(
                    systemStats = state.systemStats,
                    isLoading = state.isLoading
                )
            }

            item {
                QuickActionsRow(
                    onNewQuery = onQueryClick,
                    onNewWorkflow = onWorkflowClick
                )
            }

            item {
                Text(
                    text = "Recent Queries",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 8.dp)
                )
            }

            if (state.recentQueries.isEmpty()) {
                item {
                    EmptyStateCard(
                        message = "No recent queries",
                        actionLabel = "Start Query",
                        onAction = onQueryClick
                    )
                }
            } else {
                items(state.recentQueries.take(5)) { query ->
                    QueryHistoryCard(
                        query = query,
                        onClick = { onQueryHistoryItemClick(query.id) }
                    )
                }
            }

            item {
                Text(
                    text = "Active Workflows",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.padding(top = 8.dp)
                )
            }

            items(state.activeWorkflows.take(3)) { workflow ->
                WorkflowStatusCard(
                    workflow = workflow,
                    onClick = { /* Navigate to detail */ }
                )
            }
        }
    }
}

@Composable
fun SystemStatusCard(
    systemStats: SystemStats?,
    isLoading: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        if (isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp),
                contentAlignment = Alignment.Center
            ) {
                CircularProgressIndicator()
            }
        } else {
            Column(
                modifier = Modifier.padding(16.dp)
            ) {
                Text(
                    text = "System Status",
                    style = MaterialTheme.typography.titleMedium
                )
                Spacer(modifier = Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    StatusItem(
                        label = "Uptime",
                        value = systemStats?.uptime ?: "Unknown"
                    )
                    StatusItem(
                        label = "Active Models",
                        value = systemStats?.activeModels?.toString() ?: "0"
                    )
                    StatusItem(
                        label = "Queries/Min",
                        value = systemStats?.queriesPerMinute?.toString() ?: "0"
                    )
                    StatusItem(
                        label = "Health",
                        value = systemStats?.health ?: "Unknown",
                        valueColor = when (systemStats?.health) {
                            "healthy" -> MaterialTheme.colorScheme.primary
                            "degraded" -> MaterialTheme.colorScheme.error
                            else -> MaterialTheme.colorScheme.onSurface
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun StatusItem(
    label: String,
    value: String,
    valueColor: Color = MaterialTheme.colorScheme.onSurface
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = value,
            style = MaterialTheme.typography.headlineSmall,
            color = valueColor
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
fun QuickActionsRow(
    onNewQuery: () -> Unit,
    onNewWorkflow: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        QuickActionButton(
            modifier = Modifier.weight(1f),
            icon = Icons.Default.Edit,
            label = "New Query",
            onClick = onNewQuery
        )
        QuickActionButton(
            modifier = Modifier.weight(1f),
            icon = Icons.Default.AccountTree,
            label = "New Workflow",
            onClick = onNewWorkflow
        )
    }
}

@Composable
fun QuickActionButton(
    modifier: Modifier = Modifier,
    icon: ImageVector,
    label: String,
    onClick: () -> Unit
) {
    Card(
        modifier = modifier,
        onClick = onClick,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.secondaryContainer
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                modifier = Modifier.size(32.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.labelLarge
            )
        }
    }
}

@Composable
fun QueryHistoryCard(
    query: Query,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier.weight(1f)
            ) {
                Text(
                    text = query.text.take(50),
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 2
                )
                Spacer(modifier = Modifier.height(4.dp))
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    AssistChip(
                        onClick = { },
                        label = { Text(query.complexity, style = MaterialTheme.typography.labelSmall) }
                    )
                    Text(
                        text = "${query.latencyMs.toInt()}ms",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Icon(
                imageVector = Icons.Default.ChevronRight,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
