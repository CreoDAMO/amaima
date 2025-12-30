sealed class Screen(val route: String) {
    data object Home : Screen("home")
    data object Query : Screen("query")
    data object QueryDetail : Screen("query/{queryId}") {
        fun createRoute(queryId: String) = "query/$queryId"
    }
    data object Workflow : Screen("workflow")
    data object WorkflowDetail : Screen("workflow/{workflowId}") {
        fun createRoute(workflowId: String) = "workflow/$workflowId"
    }
    data object Models : Screen("models")
    data object Settings : Screen("settings")
    data object Login : Screen("login")
    data object Register : Screen("register")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AmaimaNavHost(
    navController: NavHostController,
    startDestination: String = Screen.Home.route,
    onDeepLink: (String) -> Unit = {}
) {
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    val bottomNavItems = listOf(
        Triple(Screen.Home, "Home", Icons.Filled.Home),
        Triple(Screen.Query, "Query", Icons.Filled.Edit),
        Triple(Screen.Workflow, "Workflow", Icons.Filled.AccountTree),
        Triple(Screen.Models, "Models", Icons.Filled.Memory)
    )

    val showBottomBar = currentRoute in bottomNavItems.map { it.first.route }

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    bottomNavItems.forEach { (screen, label, icon) ->
                        NavigationBarItem(
                            icon = { Icon(icon, contentDescription = label) },
                            label = { Text(label) },
                            selected = currentRoute == screen.route,
                            onClick = {
                                navController.navigate(screen.route) {
                                    popUpTo(Screen.Home.route) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        )
                    }
                }
            }
        }
    ) { paddingValues ->
        NavHost(
            navController = navController,
            startDestination = startDestination,
            modifier = Modifier.padding(paddingValues)
        ) {
            composable(Screen.Home.route) {
                val viewModel: HomeViewModel = hiltViewModel()
                val state by viewModel.state.collectAsState()
                val networkMonitor = NetworkMonitor.getInstance()

                HomeScreen(
                    state = state,
                    onQueryClick = { navController.navigate(Screen.Query.route) },
                    onWorkflowClick = { navController.navigate(Screen.Workflow.route) },
                    onQueryHistoryItemClick = { queryId ->
                        navController.navigate(Screen.QueryDetail.createRoute(queryId))
                    },
                    onSettingsClick = { navController.navigate(Screen.Settings.route) },
                    isOnline = networkMonitor.isOnline()
                )
            }

            composable(Screen.Query.route) {
                val viewModel: QueryViewModel = hiltViewModel()
                val state by viewModel.state.collectAsState()

                QueryScreen(
                    state = state,
                    onQueryChange = viewModel::onQueryChange,
                    onSubmitQuery = viewModel::submitQuery,
                    onProvideFeedback = viewModel::provideFeedback,
                    onClearQuery = viewModel::clearQuery,
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable(
                route = Screen.QueryDetail.route,
                arguments = listOf(
                    navArgument("queryId") { type = NavType.StringType }
                )
            ) { backStackEntry ->
                val queryId = backStackEntry.arguments?.getString("queryId") ?: ""
                val viewModel: QueryDetailViewModel = hiltViewModel()
                val state by viewModel.state.collectAsState()

                QueryDetailScreen(
                    queryId = queryId,
                    state = state,
                    onBackClick = { navController.popBackStack() }
                )
            }

            composable(Screen.Workflow.route) {
                val viewModel: WorkflowViewModel = hiltViewModel()
                val state by viewModel.state.collectAsState()

                WorkflowScreen(
                    state = state,
                    onCreateWorkflow = viewModel::createWorkflow,
                    onWorkflowClick = { workflowId ->
                        navController.navigate(Screen.WorkflowDetail.createRoute(workflowId))
                    },
                    onRefresh = viewModel::refreshWorkflows
                )
            }

            composable(Screen.Settings.route) {
                SettingsScreen(
                    onLogout = { /* Handle logout */ },
                    onClearCache = { /* Handle cache clear */ },
                    onThemeChange = { /* Handle theme change */ }
                )
            }
        }
    }
}
