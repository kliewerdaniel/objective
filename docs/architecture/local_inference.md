# Local Inference Architecture

## Overview

objective03 runs all inference locally on Apple Silicon using llama.cpp. No cloud API calls are made. This decision drives: privacy, cost savings, offline capability, deterministic reproducibility, and aesthetic consistency.

## Model Strategy

The system uses multiple specialized models rather than one universal model. This is critical for performance on consumer hardware.

| Task | Recommended Model | Quantization | GPU Layers | Context | RAM Usage |
|------|-------------------|-------------|------------|---------|-----------|
| Claim extraction | Qwen 2.5 7B Instruct | Q4_K_M | 32 | 4096 | ~5GB |
| Entity extraction | Qwen 2.5 3B Instruct | Q4_K_M | 32 | 2048 | ~2.5GB |
| Contradiction detection | Llama 3.2 3B Instruct | Q4_K_M | 32 | 4096 | ~2.5GB |
| Narrative synthesis | Llama 3.1 8B Instruct | Q4_K_M | 32 | 8192 | ~6GB |
| Broadcast writing | Qwen 2.5 14B Instruct | Q4_K_M | 32 | 8192 | ~10GB |
| Political framing | Qwen 2.5 3B Instruct | Q4_K_M | 32 | 4096 | ~2.5GB |
| Embeddings | BGE Small EN v1.5 | Q4_K_M | 0 (CPU) | 512 | ~0.5GB |
| Classification | MiniLM L6 v2 | N/A | N/A | 256 | ~0.3GB |

**Total peak memory**: ~22GB with all models loaded. The system loads/unloads models as needed to stay within the 48GB budget.

## llama.cpp Integration

The system uses `llama-cpp-python` for GPU-accelerated inference on Metal:

```python
class LLMClient:
    def __init__(self, model_path: str, config: ModelConfig):
        self.model = Llama(
            model_path=model_path,
            n_ctx=config.context,
            n_gpu_layers=config.gpu_layers,
            n_threads=config.threads or psutil.cpu_count(logical=False),
            verbose=False,
            use_mlock=True,       # Prevent swapping
            offload_kqv=True,     # Offload KQV to GPU
            flash_attn=True,      # Flash attention for long contexts
        )
        self.config = config
        self.last_used = time.monotonic()
    
    def generate(self, 
                 prompt: str, 
                 temperature: float = 0.0,
                 max_tokens: int = 512,
                 stop: list[str] = None,
                 structured: bool = False) -> LLMResponse:
        
        self.last_used = time.monotonic()
        
        kwargs = dict(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or [],
            echo=False,
        )
        
        if structured:
            kwargs["grammar"] = self._get_grammar()  # constrained decoding
        
        result = self.model.create_completion(**kwargs)
        
        return LLMResponse(
            text=result["choices"][0]["text"].strip(),
            tokens_used=result["usage"]["total_tokens"],
            tokens_per_second=result["timings"]["predicted_per_second"],
            model=self.config.name,
        )
    
    def _get_grammar(self) -> str:
        """Return GBNF grammar for structured JSON output."""
        return """
root   ::= object
object ::= "{" ws members "}" ws
members ::= member ("," ws member)*
member ::= string ":" value
string ::= "\"" ([^"]*) "\""
value  ::= string | number | object | array | "true" | "false" | "null"
number ::= [0-9]+ "."? [0-9]*
array  ::= "[" ws (value ("," ws value)*)? "]" ws
ws     ::= [ \t\n]*
"""
    
    def unload(self):
        """Release GPU memory."""
        del self.model
        gc.collect()
```

## Model Registry

The model registry manages model lifecycle (loading, caching, unloading):

```python
class ModelRegistry:
    def __init__(self, configs: dict[str, ModelConfig]):
        self.configs = configs
        self.loaded: dict[str, LLMClient] = {}
        self.max_loaded = 2  # Maximum models loaded simultaneously
        self.idle_timeout = 300  # 5 minutes before auto-unload
    
    async def get(self, task: str) -> LLMClient:
        model_name = self.configs[task].name
        if model_name in self.loaded:
            return self.loaded[model_name]
        
        # Unload least recently used if at capacity
        if len(self.loaded) >= self.max_loaded:
            self._unload_lru()
        
        # Load model
        config = self.configs[task]
        client = LLMClient(config.path, config)
        self.loaded[model_name] = client
        return client
    
    def _unload_lru(self):
        oldest = min(self.loaded.items(), key=lambda x: x[1].last_used)
        oldest[1].unload()
        del self.loaded[oldest[0]]
    
    async def maintenance(self):
        """Periodically unload idle models."""
        now = time.monotonic()
        for name, client in list(self.loaded.items()):
            if now - client.last_used > self.idle_timeout:
                client.unload()
                del self.loaded[name]
```

## Batching Strategy

Where possible, inference is batched for throughput:

| Operation | Batch Size Strategy | Max Batch Size | Reason |
|-----------|-------------------|----------------|--------|
| Claim extraction | Dynamic (wait for N docs or T seconds) | 4 | Context window limits |
| Entity extraction | Process per-document | 1 | Document-level |
| Embedding | Fixed-size batches | 32 | Small models, high throughput |
| Contradiction comparison | Pair-based | 10 pairs | LLM calls, not embed |
| Classification | Fixed-size batches | 16 | Small classifier model |

## Context Window Management

Context windows are precious on local hardware. The system employs several strategies:

### Prompt Compression

```python
class PromptBuilder:
    def compress(self, text: str, max_chars: int) -> str:
        """Lossy compression for long documents."""
        if len(text) <= max_chars:
            return text
        
        # Strategy: keep first 20% and last 10%, with summary of middle
        head_ratio = 0.20
        tail_ratio = 0.10
        head_end = int(max_chars * head_ratio)
        tail_start = len(text) - int(max_chars * tail_ratio)
        
        head = text[:head_end]
        tail = text[tail_start:]
        
        return f"{head}\n[... {len(text) - head_end - (len(text) - tail_start)} chars omitted ...]\n{tail}"
```

### Sliding Window

For very long documents, the system uses a sliding window approach:

```python
def sliding_extraction(text: str, window_size: int = 3072, overlap: int = 256):
    """Extract claims from long documents via sliding window."""
    claims = []
    start = 0
    while start < len(text):
        chunk = text[start:start + window_size]
        chunk_claims = extract_claims_from_chunk(chunk)
        claims.extend(chunk_claims)
        start += window_size - overlap
    return deduplicate_claims(claims)
```

### Context Budgeting

Each model call has a context budgeting step:

```python
def budget_context(task: str, model_config: ModelConfig, document: Document) -> str:
    """Allocate context budget based on task priority."""
    max_context = model_config.context - 256  # Reserve for output
    
    if task == "claim_extraction":
        # Priority: instructions > document > examples
        budget = {
            "system_prompt": 512,
            "document": max_context - 1024,
            "output_format": 256,
            "examples": 256,
        }
    elif task == "narrative_synthesis":
        budget = {
            "system_prompt": 1024,
            "graph_state": 4096,
            "history": 2048,
            "output": max_context - 8192,
        }
    # ...
```

## Apple Silicon Optimization

### Metal GPU Acceleration

- `n_gpu_layers >= 32` for 7B+ models
- `use_mlock=True` to prevent memory swapping
- `offload_kqv=True` for attention computation on GPU
- `flash_attn=True` for memory-efficient attention
- Batch prompts to maximize GPU utilization

### Memory Management

```python
class MemoryManager:
    def __init__(self, total_gb: float = 48.0):
        self.total = total_gb
        self.reserved = {
            "system": 4.0,      # macOS overhead
            "graph_db": 2.0,    # KuzuDB in-memory
            "vector_db": 2.0,   # Qdrant memory-mapped
            "audio_cache": 1.0, # Audio segments
        }
        self.available_for_models = total_gb - sum(self.reserved.values())
    
    def can_load(self, model_size_gb: float) -> bool:
        """Check if model fits in remaining budget."""
        currently_loaded = sum(m.size_gb for m in self.loaded_models)
        return currently_loaded + model_size_gb <= self.available_for_models
```

### Temperature and Determinism

For extraction tasks: `temperature=0.0` for deterministic output.
For synthesis tasks: `temperature=0.3-0.7` for variety while maintaining coherence.
For classification tasks: `temperature=0.0` for deterministic labels.
Seeds are configurable and recorded in audit logs for reproducibility.

## Inference Scheduling

GPU-accelerated inference is a contended resource. The scheduler manages access:

```python
class InferenceScheduler:
    def __init__(self):
        self.queue = asyncio.PriorityQueue()
        self.current_task = None
        self.lock = asyncio.Lock()
    
    async def schedule(self, priority: int, model_name: str, fn: Callable):
        """Schedule inference with priority. Lower number = higher priority."""
        event = asyncio.Event()
        await self.queue.put((priority, model_name, fn, event))
        await event.wait()
    
    async def _worker(self):
        while True:
            priority, model_name, fn, event = await self.queue.get()
            async with self.lock:
                self.current_task = model_name
                try:
                    result = await fn()
                    return result
                finally:
                    self.current_task = None
                    event.set()
```

Priority levels:
- 0 (Critical) — Health checks, emergency shutdown
- 1 (High) — Claim extraction, entity resolution
- 2 (Medium) — Contradiction detection, classification
- 3 (Low) — Narrative analysis, broadcast writing
- 4 (Background) — Embeddings, memory consolidation

## Model Download and Management

Models are managed via a CLI subcommand or config:

```yaml
models:
  manifests:
    - name: "qwen2.5-7b-instruct"
      source: "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf"
      sha256: "abcdef..."
      type: "extraction"
    - name: "bge-small-en-v1.5"
      source: "https://huggingface.co/BAAI/bge-small-en-v1.5-gguf/resolve/main/bge-small-en-v1.5-q4_k_m.gguf"
      sha256: "123456..."
      type: "embedding"
```

The `objective03 models download` command:
1. Reads model manifest
2. Verifies checksums of existing files
3. Downloads missing or corrupted models
4. Validates model compatibility with llama.cpp version
