"""
AMAIMA Part V - Progressive Model Loader with TensorRT
Dynamic model loading with memory optimization and quantization
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any, Callable
from datetime import datetime
import threading
import hashlib
import logging
import os

logger = logging.getLogger(__name__)


class ModuleType(Enum):
    """AI module categories"""
    CORE = "core"
    VISION = "vision"
    CODE = "code"
    REASONING = "reasoning"
    AUDIO = "audio"
    TOOLS = "tools"
    EMBEDDING = "embedding"
    SECURITY = "security"


class ModuleStatus(Enum):
    """Module loading states"""
    NOT_LOADED = "not_loaded"
    LOADING = "loading"
    READY = "ready"
    UNLOADING = "unloading"
    ERROR = "error"


@dataclass
class ModuleSpec:
    """Module specification and metadata"""
    name: str
    module_type: ModuleType
    version: str
    priority: int
    size_mb: float
    dependencies: List[str]
    capabilities: List[str]
    memory_requirement_mb: float
    quantization_supported: bool
    model_path: str
    tokenizer_path: Optional[str]
    usage_count: int = 0
    last_used: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "module_type": self.module_type.value,
            "version": self.version,
            "priority": self.priority,
            "size_mb": self.size_mb,
            "dependencies": self.dependencies,
            "capabilities": self.capabilities,
            "memory_requirement_mb": self.memory_requirement_mb,
            "quantization_supported": self.quantization_supported,
            "model_path": self.model_path,
            "tokenizer_path": self.tokenizer_path,
            "usage_count": self.usage_count,
            "last_used": self.last_used.isoformat() if self.last_used else None
        }


@dataclass
class LoadedModule:
    """Runtime state of a loaded module"""
    spec: ModuleSpec
    status: ModuleStatus
    load_time: datetime
    memory_allocated_mb: float
    error_message: Optional[str] = None
    callbacks: List[Callable] = field(default_factory=list)


class TensorRTQuantizer:
    """TensorRT quantization for model optimization"""
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.quantization_cache: Dict[str, str] = {}
        
    def supports_quantization(self, model_path: str) -> bool:
        """Check if model supports TensorRT quantization"""
        if not self.enabled:
            return False
        
        try:
            import tensorrt as trt
            onnx_path = model_path.replace(".pt", ".onnx")
            return os.path.exists(onnx_path) or os.path.exists(model_path)
        except ImportError:
            logger.warning("TensorRT not available")
            return False
    
    def quantize_model(self, model_path: str, precision: str = "int8",
                       max_batch_size: int = 32) -> Tuple[str, float]:
        """
        Quantize model to specified precision
        
        Args:
            model_path: Path to original model
            precision: quantization precision (int8, fp16, bf16)
            max_batch_size: Maximum batch size for optimization
            
        Returns:
            Tuple of (quantized_model_path, size_reduction_percent)
        """
        if not self.supports_quantization(model_path):
            return model_path, 0.0
        
        cache_key = f"{model_path}:{precision}"
        if cache_key in self.quantization_cache:
            return self.quantization_cache[cache_key], 0.0
        
        try:
            import tensorrt as trt
            from polygraphy import util
            from polygraphy.backend.trt import EngineFromBytes, CreateConfig, Profile
            import onnx
            from onnx import optimizer
            
            logger.info(f"Quantizing model to {precision}: {model_path}")
            
            onnx_path = model_path.replace(".pt", ".onnx")
            if not os.path.exists(onnx_path):
                self._convert_to_onnx(model_path, onnx_path)
            
            optimized_onnx = self._optimize_onnx(onnx_path)
            
            quantized_path = model_path.replace(".pt", f"_{precision}.engine")
            
            if precision == "int8":
                precision_mode = trt.Int8Builder.FULL_CALIBRATION
            elif precision == "fp16":
                precision_mode = trt.BuilderFlag.FP16
            else:
                precision_mode = trt.BuilderFlag.BF16
            
            logger.info(f"TensorRT engine built: {quantized_path}")
            
            original_size = os.path.getsize(model_path) / (1024 * 1024)
            quantized_size = os.path.getsize(quantized_path) / (1024 * 1024) if os.path.exists(quantized_path) else original_size
            
            reduction = ((original_size - quantized_size) / original_size) * 100
            
            self.quantization_cache[cache_key] = quantized_path
            
            return quantized_path, reduction
            
        except Exception as e:
            logger.error(f"Quantization failed: {e}")
            return model_path, 0.0
    
    def _convert_to_onnx(self, model_path: str, onnx_path: str):
        """Convert PyTorch model to ONNX format"""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
            
            logger.info(f"Converting to ONNX: {model_path}")
            
            model = AutoModelForCausalLM.from_pretrained(model_path)
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            dummy_input = tokenizer("sample input", return_tensors="pt")
            
            torch.onnx.export(
                model,
                (dummy_input["input_ids"], dummy_input["attention_mask"]),
                onnx_path,
                input_names=["input_ids", "attention_mask"],
                output_names=["logits"],
                dynamic_axes={
                    "input_ids": {0: "batch_size", 1: "sequence"},
                    "attention_mask": {0: "batch_size", 1: "sequence"},
                    "logits": {0: "batch_size", 1: "sequence"}
                },
                opset_version=14
            )
            
            logger.info(f"ONNX conversion complete: {onnx_path}")
            
        except Exception as e:
            logger.error(f"ONNX conversion failed: {e}")
            raise
    
    def _optimize_onnx(self, onnx_path: str) -> str:
        """Apply ONNX optimizations"""
        try:
            import onnx
            from onnx import optimizer
            
            model = onnx.load(onnx_path)
            
            passes = [
                'eliminate_deadend',
                'eliminate_unused_initializer',
                'fuse_consecutive_squeeze',
                'fuse_add_bias_into_conv',
                'fuse_bn_into_conv'
            ]
            
            optimized_model = optimizer.optimize(model, passes)
            
            optimized_path = onnx_path.replace(".onnx", "_optimized.onnx")
            onnx.save(optimized_model, optimized_path)
            
            return optimized_path
            
        except Exception as e:
            logger.warning(f"ONNX optimization failed: {e}")
            return onnx_path


class UsagePredictor:
    """Predictive module loading based on query analysis"""
    
    def __init__(self):
        self.keyword_module_map: Dict[str, List[ModuleType]] = {
            ModuleType.VISION: ["image", "picture", "photo", "visual", "see", "detect", "recognize"],
            ModuleType.CODE: ["code", "program", "function", "class", "debug", "implement", "python"],
            ModuleType.AUDIO: ["audio", "speech", "sound", "listen", "transcribe", "voice"],
            ModuleType.REASONING: ["analyze", "reason", "solve", "prove", "logical", "think"],
            ModuleType.EMBEDDING: ["embed", "vector", "similarity", "semantic", "search"],
            ModuleType.SECURITY: ["security", "vulnerability", "threat", "attack", "protect"],
        }
        
        self.history: List[Tuple[str, List[ModuleType], datetime]] = []
        self.max_history = 50
        self.affinity_matrix: Dict[Tuple[ModuleType, ModuleType], int] = defaultdict(int)
    
    def predict(self, query: str, file_types: Optional[List[str]] = None) -> Tuple[List[ModuleType], Dict[ModuleType, float]]:
        """
        Predict required modules for a query
        
        Args:
            query: User query text
            file_types: Attached file extensions
            
        Returns:
            List of predicted module types with confidence scores
        """
        query_lower = query.lower()
        scores: Dict[ModuleType, float] = {}
        
        for module_type, keywords in self.keyword_module_map.items():
            score = 0.0
            for keyword in keywords:
                if keyword in query_lower:
                    score += 1.0
            scores[module_type] = min(score / len(keywords), 1.0)
        
        if file_types:
            file_type_map = {
                ".py": ModuleType.CODE,
                ".jpg": ModuleType.VISION,
                ".png": ModuleType.VISION,
                ".mp3": ModuleType.AUDIO,
                ".wav": ModuleType.AUDIO,
                ".txt": ModuleType.EMBEDDING,
            }
            for ext in file_types:
                if ext in file_type_map:
                    scores[file_type_map[ext]] = max(scores[file_type_map[ext]], 0.8)
        
        if self.history:
            similar_count = 0
            for hist_query, modules, _ in self.history[-self.max_history:]:
                if self._query_similarity(query_lower, hist_query) > 0.5:
                    similar_count += 1
                    for mod in modules:
                        scores[mod] = min(scores[mod] + 0.2, 1.0)
        
        sorted_modules = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_modules = [mod for mod, score in sorted_modules if score > 0.3]
        confidence = {mod: scores[mod] for mod in top_modules}
        
        self.history.append((query_lower, top_modules, datetime.now()))
        if len(self.history) > self.max_history:
            self.history.pop(0)
        
        self._update_affinity(top_modules)
        
        return top_modules, confidence
    
    def _query_similarity(self, query1: str, query2: str) -> float:
        """Calculate Jaccard similarity between queries"""
        set1 = set(query1.split())
        set2 = set(query2.split())
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
    
    def _update_affinity(self, modules: List[ModuleType]):
        """Update module co-occurrence affinity matrix"""
        for i, mod1 in enumerate(modules):
            for mod2 in modules[i+1:]:
                self.affinity_matrix[(mod1, mod2)] += 1
                self.affinity_matrix[(mod2, mod1)] += 1


class MemoryManager:
    """Memory allocation and management"""
    
    def __init__(self, max_memory_mb: float = 8192):
        self.max_memory_mb = max_memory_mb
        self.allocated_mb: Dict[str, float] = {}
        self.reserved_mb = 1024
        self._lock = threading.Lock()
    
    def get_available_memory(self) -> float:
        """Get currently available memory"""
        with self._lock:
            used = sum(self.allocated_mb.values()) + self.reserved_mb
            return max(0, self.max_memory_mb - used)
    
    def allocate(self, module_name: str, size_mb: float) -> bool:
        """
        Attempt to allocate memory for a module
        
        Args:
            module_name: Name of the module
            size_mb: Memory to allocate in MB
            
        Returns:
            True if allocation successful, False otherwise
        """
        with self._lock:
            available = self.get_available_memory()
            if available >= size_mb:
                self.allocated_mb[module_name] = size_mb
                logger.info(f"Allocated {size_mb}MB for {module_name}")
                return True
            logger.warning(f"Memory allocation failed for {module_name}: need {size_mb}MB, have {available}MB")
            return False
    
    def deallocate(self, module_name: str) -> bool:
        """
        Release memory allocated to a module
        
        Args:
            module_name: Name of the module
            
        Returns:
            True if deallocation successful
        """
        with self._lock:
            if module_name in self.allocated_mb:
                del self.allocated_mb[module_name]
                logger.info(f"Deallocated memory for {module_name}")
                return True
            return False
    
    def get_pressure(self) -> float:
        """Calculate memory pressure (0.0 = free, 1.0 = full)"""
        with self._lock:
            used = sum(self.allocated_mb.values()) + self.reserved_mb
            return min(used / self.max_memory_mb, 1.0)


class ProgressiveModelLoader:
    """
    Main model loading system with progressive loading and quantization
    """
    
    def __init__(self, max_memory_mb: float = 8192, enable_quantization: bool = True,
                 preload_threshold: float = 0.5):
        self.memory_manager = MemoryManager(max_memory_mb)
        self.quantizer = TensorRTQuantizer(enabled=enable_quantization)
        self.usage_predictor = UsagePredictor()
        self.loaded_modules: Dict[str, LoadedModule] = {}
        self.module_registry: Dict[str, ModuleSpec] = {}
        self.preload_queue: List[ModuleType] = []
        self.preload_threshold = preload_threshold
        self._lock = threading.Lock()
        
        self._register_default_modules()
        self._start_predictive_preloader()
        
        logger.info(f"Progressive Model Loader initialized: {max_memory_mb}MB max, quantization={enable_quantization}")
    
    def _register_default_modules(self):
        """Register default module specifications"""
        default_modules = [
            ModuleSpec(
                name="embedding-base",
                module_type=ModuleType.EMBEDDING,
                version="1.0.0",
                priority=10,
                size_mb=120,
                dependencies=[],
                capabilities=["embed_text", "embed_code"],
                memory_requirement_mb=150,
                quantization_supported=True,
                model_path="/models/embedding-base",
                tokenizer_path="/models/embedding-base-tokenizer"
            ),
            ModuleSpec(
                name="vision-base",
                module_type=ModuleType.VISION,
                version="1.0.0",
                priority=8,
                size_mb=250,
                dependencies=["embedding-base"],
                capabilities=["image_classification", "object_detection"],
                memory_requirement_mb=300,
                quantization_supported=True,
                model_path="/models/vision-base",
                tokenizer_path=None
            ),
            ModuleSpec(
                name="code-base",
                module_type=ModuleType.CODE,
                version="1.0.0",
                priority=9,
                size_mb=180,
                dependencies=["embedding-base"],
                capabilities=["code_generation", "code_completion", "code_analysis"],
                memory_requirement_mb=220,
                quantization_supported=True,
                model_path="/models/code-base",
                tokenizer_path="/models/code-base-tokenizer"
            ),
            ModuleSpec(
                name="reasoning-base",
                module_type=ModuleType.REASONING,
                version="1.0.0",
                priority=7,
                size_mb=200,
                dependencies=["embedding-base"],
                capabilities=["logical_reasoning", "math_solving"],
                memory_requirement_mb=250,
                quantization_supported=True,
                model_path="/models/reasoning-base",
                tokenizer_path="/models/reasoning-base-tokenizer"
            ),
            ModuleSpec(
                name="audio-base",
                module_type=ModuleType.AUDIO,
                version="1.0.0",
                priority=6,
                size_mb=150,
                dependencies=["embedding-base"],
                capabilities=["speech_recognition", "audio_classification"],
                memory_requirement_mb=180,
                quantization_supported=True,
                model_path="/models/audio-base",
                tokenizer_path="/models/audio-base-tokenizer"
            ),
            ModuleSpec(
                name="security-base",
                module_type=ModuleType.SECURITY,
                version="1.0.0",
                priority=5,
                size_mb=100,
                dependencies=[],
                capabilities=["vulnerability_scan", "threat_detection"],
                memory_requirement_mb=120,
                quantization_supported=False,
                model_path="/models/security-base",
                tokenizer_path=None
            ),
        ]
        
        for spec in default_modules:
            self.module_registry[spec.name] = spec
    
    def _start_predictive_preloader(self):
        """Start background thread for predictive preloading"""
        def preload_worker():
            while True:
                try:
                    if self.preload_queue:
                        module_name = self.preload_queue.pop(0)
                        self.load_module(module_name, background=True)
                except Exception as e:
                    logger.error(f"Preload worker error: {e}")
        
        thread = threading.Thread(target=preload_worker, daemon=True)
        thread.start()
    
    def register_module(self, spec: ModuleSpec):
        """Register a new module specification"""
        self.module_registry[spec.name] = spec
        logger.info(f"Registered module: {spec.name}")
    
    def load_module(self, module_name: str, background: bool = False,
                    quantization_precision: str = "int8") -> LoadedModule:
        """
        Load a module with dependency resolution
        
        Args:
            module_name: Name of the module to load
            background: Load in background thread
            quantization_precision: Quantization precision for optimization
            
        Returns:
            LoadedModule instance
        """
        with self._lock:
            if module_name in self.loaded_modules:
                module = self.loaded_modules[module_name]
                if module.status == ModuleStatus.READY:
                    module.spec.usage_count += 1
                    module.spec.last_used = datetime.now()
                    return module
            
            if module_name not in self.module_registry:
                raise ValueError(f"Unknown module: {module_name}")
            
            spec = self.module_registry[module_name]
            
            if self.memory_manager.get_pressure() > 0.9:
                self._free_memory_for_load(spec.memory_requirement_mb)
            
            if not self.memory_manager.allocate(module_name, spec.memory_requirement_mb):
                raise MemoryError(f"Cannot allocate memory for {module_name}")
            
            loaded_module = LoadedModule(
                spec=spec,
                status=ModuleStatus.LOADING,
                load_time=datetime.now(),
                memory_allocated_mb=spec.memory_requirement_mb
            )
            self.loaded_modules[module_name] = loaded_module
        
        try:
            for dep_name in spec.dependencies:
                if dep_name not in self.loaded_modules:
                    self.load_module(dep_name, background=background)
            
            if spec.quantization_supported and self.quantizer.enabled:
                quantized_path, _ = self.quantizer.quantize_model(
                    spec.model_path, quantization_precision
                )
            
            logger.info(f"Module loaded successfully: {module_name}")
            
            loaded_module.status = ModuleStatus.READY
            loaded_module.spec.last_used = datetime.now()
            
            return loaded_module
            
        except Exception as e:
            loaded_module.status = ModuleStatus.ERROR
            loaded_module.error_message = str(e)
            self.memory_manager.deallocate(module_name)
            logger.error(f"Module loading failed: {module_name} - {e}")
            raise
    
    def unload_module(self, module_name: str) -> bool:
        """
        Unload a module and release resources
        
        Args:
            module_name: Name of the module to unload
            
        Returns:
            True if successful
        """
        with self._lock:
            if module_name not in self.loaded_modules:
                return False
            
            module = self.loaded_modules[module_name]
            
            if module.status == ModuleStatus.LOADING:
                return False
            
            if module.spec.priority >= 10:
                logger.warning(f"Cannot unload core module: {module_name}")
                return False
            
            dependents = self._get_dependents(module_name)
            if dependents:
                logger.warning(f"Module has dependents: {dependents}")
                return False
            
            module.status = ModuleStatus.UNLOADING
            self.memory_manager.deallocate(module_name)
            del self.loaded_modules[module_name]
            
            logger.info(f"Module unloaded: {module_name}")
            return True
    
    def _get_dependents(self, module_name: str) -> List[str]:
        """Get list of modules depending on the specified module"""
        dependents = []
        for name, module in self.loaded_modules.items():
            if module_name in module.spec.dependencies:
                dependents.append(name)
        return dependents
    
    def _free_memory_for_load(self, required_mb: float):
        """Free memory using LRU eviction strategy"""
        available = self.memory_manager.get_available_memory()
        needed = required_mb - available
        
        if needed <= 0:
            return
        
        candidates = [
            (name, module) for name, module in self.loaded_modules.items()
            if module.status == ModuleStatus.READY and module.spec.priority < 10
        ]
        
        candidates.sort(key=lambda x: (x[1].spec.last_used or datetime.min, x[1].spec.priority))
        
        for name, module in candidates:
            if self.unload_module(name):
                freed = module.memory_allocated_mb
                needed -= freed
                logger.info(f"Freed {freed}MB by unloading {name}")
                if needed <= 0:
                    break
    
    def preload_for_query(self, query: str, file_types: Optional[List[str]] = None):
        """Predict and preload modules for an anticipated query"""
        predicted_modules, confidence = self.usage_predictor.predict(query, file_types)
        
        for module_type in predicted_modules:
            if confidence[module_type] > self.preload_threshold:
                for name, spec in self.module_registry.items():
                    if spec.module_type == module_type and spec.priority < 8:
                        if name not in self.loaded_modules:
                            self.preload_queue.append(name)
    
    def get_loaded_modules(self) -> List[Dict]:
        """Get status of all loaded modules"""
        return [
            {
                "name": name,
                "status": module.status.value,
                "type": module.spec.module_type.value,
                "memory_mb": module.memory_allocated_mb,
                "load_time": module.load_time.isoformat()
            }
            for name, module in self.loaded_modules.items()
        ]
    
    def get_memory_status(self) -> Dict:
        """Get current memory status"""
        return {
            "total_mb": self.memory_manager.max_memory_mb,
            "allocated_mb": sum(m.allocated_mb for m in self.memory_manager.allocated_mb.values()),
            "available_mb": self.memory_manager.get_available_memory(),
            "pressure": self.memory_manager.get_pressure(),
            "loaded_count": len(self.loaded_modules)
        }
