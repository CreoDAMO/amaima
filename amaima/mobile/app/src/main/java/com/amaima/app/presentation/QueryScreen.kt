@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun QueryScreen(
    state: QueryState,
    onQueryChange: (String) -> Unit,
    onSubmitQuery: () -> Unit,
    onProvideFeedback: (Feedback) -> Unit,
    onClearQuery: () -> Unit,
    onBackClick: () -> Unit
) {
    val scrollState = rememberScrollState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("New Query") },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(Icons.Default.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    if (state.query.isNotEmpty()) {
                        IconButton(onClick = onClearQuery) {
                            Icon(Icons.Default.Clear, contentDescription = "Clear")
                        }
                    }
                }
            )
        }
    ) { paddingValues ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            Column(
                modifier = Modifier
                    .weight(1f)
                    .padding(16.dp)
                    .verticalScroll(scrollState)
            ) {
                OutlinedTextField(
                    value = state.query,
                    onValueChange = onQueryChange,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 150.dp),
                    placeholder = { Text("Enter your query...") },
                    supportingText = {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text("${state.query.length} / 10000")
                            Text(state.currentComplexity)
                        }
                    },
                    enabled = state.status != QueryStatus.PROCESSING,
                    maxLines = 10
                )

                Spacer(modifier = Modifier.height(16.dp))

                OperationTypeSelector(
                    selectedType = state.selectedOperation,
                    onTypeSelected = { /* Handle operation type selection */ }
                )

                Spacer(modifier = Modifier.height(16.dp))

                FileAttachmentSection(
                    attachedFiles = state.attachedFiles,
                    onAttachFile = { /* Handle file attachment */ },
                    onRemoveFile = { /* Handle file removal */ }
                )

                if (state.status == QueryStatus.ERROR) {
                    Spacer(modifier = Modifier.height(16.dp))
                    ErrorCard(
                        message = state.errorMessage ?: "An error occurred",
                        onRetry = onSubmitQuery
                    )
                }
            }

            QuerySubmissionBar(
                status = state.status,
                canSubmit = state.query.isNotBlank() && state.status != QueryStatus.PROCESSING,
                onSubmit = onSubmitQuery
            )

            if (state.status == QueryStatus.COMPLETED && state.response != null) {
                ResponseCard(
                    response = state.response,
                    onProvideFeedback = onProvideFeedback
                )
            }
        }
    }
}

@Composable
fun OperationTypeSelector(
    selectedType: String,
    onTypeSelected: (String) -> Unit
) {
    val operationTypes = listOf(
        "general" to "General",
        "code" to "Code Generation",
        "analysis" to "Analysis",
        "creative" to "Creative",
        "qa" to "Question Answering"
    )

    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        items(operationTypes) { (value, label) ->
            FilterChip(
                selected = selectedType == value,
                onClick = { onTypeSelected(value) },
                label = { Text(label) }
            )
        }
    }
}

@Composable
fun FileAttachmentSection(
    attachedFiles: List<AttachedFile>,
    onAttachFile: () -> Unit,
    onRemoveFile: (AttachedFile) -> Unit
) {
    Column {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Attachments",
                style = MaterialTheme.typography.titleSmall
            )
            TextButton(onClick = onAttachFile) {
                Icon(Icons.Default.AttachFile, contentDescription = null)
                Spacer(modifier = Modifier.width(4.dp))
                Text("Add File")
            }
        }

        if (attachedFiles.isNotEmpty()) {
            Spacer(modifier = Modifier.height(8.dp))
            attachedFiles.forEach { file ->
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Icon(
                        imageVector = when (file.mimeType) {
                            "image/*" -> Icons.Default.Image
                            "text/*" -> Icons.Default.Description
                            else -> Icons.Default.InsertDriveFile
                        },
                        contentDescription = null,
                        modifier = Modifier.size(20.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = file.name,
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.bodySmall
                    )
                    IconButton(
                        onClick = { onRemoveFile(file) },
                        modifier = Modifier.size(24.dp)
                    ) {
                        Icon(
                            Icons.Default.Close,
                            contentDescription = "Remove",
                            modifier = Modifier.size(16.dp)
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun ResponseCard(
    response: QueryResponse,
    onProvideFeedback: (Feedback) -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp)
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Response",
                    style = MaterialTheme.typography.titleMedium
                )
                ConfidenceBadge(confidence = response.confidence)
            }

            Spacer(modifier = Modifier.height(12.dp))

            Text(
                text = response.responseText,
                style = MaterialTheme.typography.bodyMedium
            )

            Spacer(modifier = Modifier.height(16.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Model: ${response.modelUsed}",
                        style = MaterialTheme.typography.labelSmall
                    )
                    Text(
                        text = "Latency: ${response.latencyMs.toInt()}ms",
                        style = MaterialTheme.typography.labelSmall
                    )
                }

                FeedbackButtons(
                    onPositiveFeedback = {
                        onProvideFeedback(Feedback(FeedbackType.THUMBS_UP))
                    },
                    onNegativeFeedback = {
                        onProvideFeedback(Feedback(FeedbackType.THUMBS_DOWN))
                    }
                )
            }
        }
    }
}

@Composable
fun ConfidenceBadge(confidence: Float) {
    val (color, label) = when {
        confidence >= 0.9f -> MaterialTheme.colorScheme.primary to "High"
        confidence >= 0.7f -> MaterialTheme.colorScheme.tertiary to "Medium"
        else -> MaterialTheme.colorScheme.error to "Low"
    }

    Surface(
        color = color.copy(alpha = 0.1f),
        shape = MaterialTheme.shapes.small
    ) {
        Text(
            text = "$label (${(confidence * 100).toInt()}%)",
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelSmall,
            color = color
        )
    }
}

@Composable
fun FeedbackButtons(
    onPositiveFeedback: () -> Unit,
    onNegativeFeedback: () -> Unit
) {
    Row {
        IconButton(onClick = onPositiveFeedback) {
            Icon(
                Icons.Default.ThumbUp,
                contentDescription = "Positive feedback",
                tint = MaterialTheme.colorScheme.primary
            )
        }
        IconButton(onClick = onNegativeFeedback) {
            Icon(
                Icons.Default.ThumbDown,
                contentDescription = "Negative feedback",
                tint = MaterialTheme.colorScheme.error
            )
        }
    }
}

@Composable
fun QuerySubmissionBar(
    status: QueryStatus,
    canSubmit: Boolean,
    onSubmit: () -> Unit
) {
    Surface(
        tonalElevation = 3.dp,
        shadowElevation = 8.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            when (status) {
                QueryStatus.IDLE -> {
                    Text(
                        text = "Ready to submit",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Button(
                        onClick = onSubmit,
                        enabled = canSubmit
                    ) {
                        Icon(Icons.Default.Send, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("Submit")
                    }
                }
                QueryStatus.PROCESSING -> {
                    LinearProgressIndicator(
                        modifier = Modifier
                            .weight(1f)
                            .padding(end = 16.dp)
                    )
                    Text(
                        text = "Processing...",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
                QueryStatus.COMPLETED -> {
                    Text(
                        text = "Query complete",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                    OutlinedButton(onClick = onSubmit) {
                        Text("Submit New")
                    }
                }
                QueryStatus.ERROR -> {
                    Text(
                        text = "Error occurred",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                    Button(onClick = onSubmit) {
                        Text("Retry")
                    }
                }
            }
        }
    }
}
