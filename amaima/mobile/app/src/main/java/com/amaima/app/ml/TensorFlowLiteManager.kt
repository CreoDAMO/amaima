class TensorFlowLiteManager(
    private val context: Context,
    private val modelDownloader: ModelDownloader
) {
    private val models = ConcurrentHashMap<String, TensorFlowLiteModel>()
    private val interpreterMap = ConcurrentHashMap<String, Interpreter>()

    companion object {
        private const val MODEL_CACHE_SIZE = 500L * 1024 * 1024 // 500MB
        private const val MODEL_VERSION = "1.0.0"
    }

    data class TensorFlowLiteModel(
        val name: String,
        val version: String,
        val modelPath: String,
        val inputShape: IntArray,
        val outputShape: IntArray,
        val labels: List<String>
    ) {
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (javaClass != other?.javaClass) return false
            other as TensorFlowLiteModel
            return name == other.name && version == other.version
        }

        override fun hashCode(): Int {
            var result = name.hashCode()
            result = 31 * result + version.hashCode()
            return result
        }
    }

    suspend fun loadDefaultModels() {
        val defaultModels = listOf(
            TensorFlowLiteModel(
                name = "complexity_estimator",
                version = MODEL_VERSION,
                modelPath = "models/complexity_estimator.tflite",
                inputShape = intArrayOf(1, 128),
                outputShape = intArrayOf(1, 5),
                labels = listOf("TRIVIAL", "SIMPLE", "MODERATE", "COMPLEX", "EXPERT")
            ),
            TensorFlowLiteModel(
                name = "keyword_extractor",
                version = MODEL_VERSION,
                modelPath = "models/keyword_extractor.tflite",
                inputShape = intArrayOf(1, 64),
                outputShape = intArrayOf(1, 10),
                labels = emptyList()
            ),
            TensorFlowLiteModel(
                name = "sentiment_analyzer",
                version = MODEL_VERSION,
                modelPath = "models/sentiment_analyzer.tflite",
                inputShape = intArrayOf(1, 128),
                outputShape = intArrayOf(1, 3),
                labels = listOf("NEGATIVE", "NEUTRAL", "POSITIVE")
            )
        )

        defaultModels.forEach { model ->
            loadModel(model)
        }
    }

    suspend fun loadModel(model: TensorFlowLiteModel) {
        withContext(Dispatchers.IO) {
            try {
                val modelFile = File(context.filesDir, model.modelPath)
                
                if (!modelFile.exists()) {
                    val downloaded = modelDownloader.downloadModel(model.name, modelFile)
                    if (!downloaded) {
                        Log.w(TAG, "Failed to download model: ${model.name}")
                        return@withContext
                    }
                }

                val options = Interpreter.Options().apply {
                    setNumThreads(4)
                }

                val interpreter = Interpreter(modelFile, options)
                interpreterMap[model.name] = interpreter
                models[model.name] = model
                
                Log.d(TAG, "Model loaded: ${model.name}")
            } catch (e: Exception) {
                Log.e(TAG, "Failed to load model: ${model.name}", e)
            }
        }
    }

    fun estimateComplexity(query: String): ComplexityResult {
        val interpreter = interpreterMap["complexity_estimator"]
            ?: return ComplexityResult(
                complexity = "MODERATE",
                confidence = 0.5f,
                method = "default"
            )

        return try {
            val input = preprocessQuery(query)
            val output = Array(1) { FloatArray(5) }
            interpreter.run(input, output)

            val probabilities = output[0]
            val maxIndex = probabilities.indices.maxByOrNull { probabilities[it] } ?: 2

            val complexity = when (maxIndex) {
                0 -> "TRIVIAL"
                1 -> "SIMPLE"
                2 -> "MODERATE"
                3 -> "COMPLEX"
                4 -> "EXPERT"
                else -> "MODERATE"
            }

            ComplexityResult(
                complexity = complexity,
                confidence = probabilities[maxIndex],
                method = "ml_model"
            )
        } catch (e: Exception) {
            Log.e(TAG, "Complexity estimation failed", e)
            ComplexityResult("MODERATE", 0.5f, "fallback")
        }
    }

    fun analyzeSentiment(text: String): SentimentResult {
        val interpreter = interpreterMap["sentiment_analyzer"]
            ?: return SentimentResult("NEUTRAL", 0.5f)

        return try {
            val input = preprocessText(text)
            val output = Array(1) { FloatArray(3) }
            interpreter.run(input, output)

            val probabilities = output[0]
            val maxIndex = probabilities.indices.maxByOrNull { probabilities[it] } ?: 1

            val sentiment = when (maxIndex) {
                0 -> "NEGATIVE"
                1 -> "NEUTRAL"
                2 -> "POSITIVE"
                else -> "NEUTRAL"
            }

            SentimentResult(sentiment, probabilities[maxIndex])
        } catch (e: Exception) {
            Log.e(TAG, "Sentiment analysis failed", e)
            SentimentResult("NEUTRAL", 0.5f)
        }
    }

    private fun preprocessQuery(query: String): Array<FloatArray> {
        val tokens = query.lowercase()
            .replace(Regex("[^a-z0-9\\s]"), "")
            .split("\\s+")
            .take(128)

        val vector = FloatArray(128) { 0f }
        tokens.forEachIndexed { index, token ->
            vector[index] = token.hashCode().toFloat() / Float.MAX_VALUE
        }

        return arrayOf(vector)
    }

    private fun preprocessText(text: String): Array<FloatArray> {
        return preprocessQuery(text)
    }

    fun getLoadedModels(): List<String> {
        return models.keys.toList()
    }

    fun isModelLoaded(modelName: String): Boolean {
        return interpreterMap.containsKey(modelName)
    }

    suspend fun unloadModel(modelName: String) {
        withContext(Dispatchers.IO) {
            interpreterMap.remove(modelName)?.close()
            models.remove(modelName)
            Log.d(TAG, "Model unloaded: $modelName")
        }
    }

    fun clearAllModels() {
        interpreterMap.values.forEach { it.close() }
        interpreterMap.clear()
        models.clear()
    }

    data class ComplexityResult(
        val complexity: String,
        val confidence: Float,
        val method: String
    )

    data class SentimentResult(
        val sentiment: String,
        val confidence: Float
    )
}
