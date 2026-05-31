"""Daemon orchestrator — manages component lifecycle."""

import asyncio
import signal
import time
import structlog
from enum import Enum
from typing import Optional

from src.config import Config
from src.database.graph import GraphStore
from src.database.vector import VectorStore
from src.database.metadata import MetadataStore
from src.models.client import ModelRegistry
from src.audio.piper import QwenTTS, AudioCache
from src.audio.player import AudioQueue, ContinuousPlayer, AudioStitcher, StreamingAudioQueue, StreamingPlayer
from src.audio.ambient import AmbientGenerator


logger = structlog.get_logger()


class SystemState(Enum):
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    SHUTDOWN = "shutdown"


class ComponentStatus(Enum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


class Orchestrator:
    def __init__(self, config: Config, headless: bool = False):
        self.config = config
        self.state = SystemState.STARTING
        self.components: dict[str, any] = {}
        self.start_time = time.monotonic()
        self._background_tasks: list[asyncio.Task] = []
        self.activity_log: list[dict] = []  # Shared activity log for the dashboard
        self._shared_state: dict = {}  # Shared state across all agent tasks
        self.headless = headless

    def log_activity(self, message: str, level: str = "info"):
        """Append a timestamped activity entry."""
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "message": message,
            "level": level,
        }
        self.activity_log.append(entry)
        if len(self.activity_log) > 200:
            self.activity_log.pop(0)

    async def bootstrap(self):
        self.log_activity("Bootstrap starting...")
        logger.info("orchestrator.bootstrap.start")
        print("[objective03] Bootstrapping system...")

        # Metadata store
        try:
            self.components["metadata"] = MetadataStore(self.config.metadata.path)
            self.log_activity("Metadata store initialized")
            print("[objective03]   [OK] Metadata store")
        except Exception as e:
            logger.warning("orchestrator.metadata.failed", error=str(e))
            print(f"[objective03]   [FAIL] Metadata store: {e}")

        # Graph database
        try:
            self.components["graph"] = GraphStore(
                self.config.databases.path,
                buffer_pool_size=self.config.databases.buffer_pool_size,
                max_threads=self.config.databases.max_threads,
            )
            self.log_activity("Graph database (KuzuDB) initialized")
            print("[objective03]   [OK] Graph database (KuzuDB)")
        except Exception as e:
            logger.warning("orchestrator.graph.failed", error=str(e))
            print(f"[objective03]   [FAIL] Graph database: {e}")

        # Vector store
        try:
            self.components["vector"] = VectorStore(
                host=self.config.vector.host,
                port=self.config.vector.port,
                collection=self.config.vector.collection,
                vector_size=self.config.vector.vector_size,
            )
            self.log_activity("Vector store (Qdrant) initialized")
            print("[objective03]   [OK] Vector store (Qdrant)")
        except Exception as e:
            logger.warning("orchestrator.vector.failed", error=str(e))
            print(f"[objective03]   [WARN] Vector store unavailable: {e}")

        # Model registry
        try:
            self.components["model_registry"] = ModelRegistry(self.config.models)
            self.log_activity("Model registry initialized")
            print("[objective03]   [OK] Model registry")
        except Exception as e:
            logger.warning("orchestrator.models.failed", error=str(e))
            print(f"[objective03]   [WARN] Model registry: {e}")

        # Audio pipeline
        if self.config.audio.enabled:
            try:
                self.components["tts"] = QwenTTS(self.config.audio)
                cache_dir = self.config.audio_dir / "cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                self.components["audio_cache"] = AudioCache(cache_dir)
                self.components["audio_queue"] = AudioQueue()
                self.components["audio_stitcher"] = AudioStitcher()
                self.components["audio_player"] = ContinuousPlayer(
                    self.components["audio_queue"],
                    self.config.audio.sample_rate,
                )
                # Streaming components for chunk-level playback
                streaming_queue = StreamingAudioQueue()
                self.components["streaming_queue"] = streaming_queue
                streaming_player = StreamingPlayer(
                    streaming_queue,
                    self.config.audio.sample_rate,
                )
                self.components["streaming_player"] = streaming_player
                self.components["ambient"] = AmbientGenerator(self.config.audio.sample_rate)
                self.log_activity("Audio pipeline initialized (streaming)")
                print("[objective03]   [OK] Audio pipeline (streaming)")
            except Exception as e:
                logger.warning("orchestrator.audio.failed", error=str(e))
                print(f"[objective03]   [WARN] Audio pipeline: {e}")

        # Create agents
        try:
            from src.agents.claim_extractor import ClaimExtractor
            from src.agents.entity_extractor import EntityExtractor
            from src.agents.contradiction_detector import ContradictionDetector
            from src.agents.narrative_analyzer import NarrativeAnalyzer
            from src.agents.broadcast_writer import BroadcastWriter
            from src.agents.event_clustering import EventClusteringEngine
            from src.agents.source_reliability import SourceReliabilityEvaluator
            from src.agents.framing_analyzer import FramingAnalyzer
            from src.agents.ingestion_coordinator import IngestionCoordinator
            from src.agents.memory_consolidator import MemoryConsolidator
            from src.agents.graph_updater import GraphUpdater
            from src.agents.audio_producer import AudioProducer
            from src.evaluation.engine import EvaluationEngine

            self.components["agents"] = {
                "ingestion_coordinator": IngestionCoordinator(),
                "memory_consolidator": MemoryConsolidator(),
                "claim_extractor": ClaimExtractor(),
                "entity_extractor": EntityExtractor(),
                "contradiction_detector": ContradictionDetector(),
                "narrative_analyzer": NarrativeAnalyzer(),
                "broadcast_writer": BroadcastWriter(),
                "event_clustering": EventClusteringEngine(),
                "source_reliability": SourceReliabilityEvaluator(),
                "framing_analyzer": FramingAnalyzer(),
                "graph_updater": GraphUpdater(),
                "audio_producer": AudioProducer(),
                "evaluation_engine": EvaluationEngine(),
            }
            self.log_activity(f"Registered {len(self.components['agents'])} agents")
            print(f"[objective03]   [OK] {len(self.components['agents'])} agents registered")
        except Exception as e:
            logger.warning("orchestrator.agents.failed", error=str(e))
            print(f"[objective03]   [WARN] Agent registration: {e}")
            self.components["agents"] = {}

        # Scheduler daemon
        try:
            from src.agents.scheduler_daemon import SchedulerDaemon
            scheduler = SchedulerDaemon()
            scheduler.register(ScheduledTask(
                "ingestion", self._run_agent("ingestion_coordinator"),
                self.config.scheduler.ingestion_interval,
            ))
            scheduler.register(ScheduledTask(
                "analysis", self._run_analysis_pipeline,
                self.config.scheduler.analysis_interval,
                run_immediately=False,
            ))
            scheduler.register(ScheduledTask(
                "broadcast", self._run_agent("broadcast_writer"),
                self.config.scheduler.broadcast_interval,
                run_immediately=False,
            ))
            scheduler.register(ScheduledTask(
                "audio", self._run_agent("audio_producer"),
                self.config.scheduler.broadcast_interval,
                run_immediately=False,
                max_failures=10,
                max_runtime=600.0,
            ))
            scheduler.register(ScheduledTask(
                "consolidation", self._run_agent("memory_consolidator"),
                self.config.scheduler.consolidation_interval,
                run_immediately=False,
            ))
            scheduler.register(ScheduledTask(
                "evaluation", self._run_agent("evaluation_engine"),
                self.config.scheduler.consolidation_interval,
                run_immediately=False,
            ))
            self.components["scheduler"] = scheduler
            self.log_activity("Scheduler initialized with 5 tasks")
            print("[objective03]   [OK] Scheduler (5 tasks)")
        except Exception as e:
            logger.warning("orchestrator.scheduler.failed", error=str(e))
            print(f"[objective03]   [WARN] Scheduler: {e}")

        # Start background tasks
        self._background_tasks.append(asyncio.create_task(self._scheduler_loop()))
        self._background_tasks.append(asyncio.create_task(self._health_check()))
        self.log_activity("Background tasks started")
        print("[objective03]   [OK] Background tasks started")

        if self.config.audio.enabled and "audio_player" in self.components:
            self._background_tasks.append(asyncio.create_task(
                self.components["audio_player"].run()
            ))
            print("[objective03]   [OK] Audio player started")
        if self.config.audio.enabled and "streaming_player" in self.components:
            self._background_tasks.append(asyncio.create_task(
                self.components["streaming_player"].run()
            ))
            print("[objective03]   [OK] Streaming player started")

        # Start dashboard
        if not self.headless:
            try:
                from src.ui.dashboard import RichDashboard
                dashboard = RichDashboard(orchestrator=self)
                self.components["dashboard"] = dashboard
                self._background_tasks.append(asyncio.create_task(self._run_dashboard(dashboard)))
                logger.info("orchestrator.dashboard.started")
                self.log_activity("Dashboard UI started")
                print("[objective03]   [OK] Dashboard UI")
            except Exception as e:
                logger.warning("orchestrator.dashboard.failed", error=str(e))
                print(f"[objective03]   [WARN] Dashboard: {e}")
        else:
            print("[objective03]   [OK] Dashboard disabled (headless mode)")

        self.state = SystemState.RUNNING
        logger.info("orchestrator.bootstrap.complete", state=self.state.value)
        self.log_activity("System running — awaiting scheduled tasks")
        print("[objective03] System RUNNING — press Ctrl+C to stop")

    async def run(self):
        logger.info("orchestrator.run.start")
        tick = 0
        while self.state != SystemState.SHUTDOWN:
            if self.headless and tick % 30 == 0:
                agents_ok = len(self.components.get("agents", {}))
                graph_ok = "graph" in self.components
                meta_ok = "metadata" in self.components
                print(f"[objective03] tick={tick}s agents={agents_ok} graph={'ok' if graph_ok else 'fail'} meta={'ok' if meta_ok else 'fail'}")
            await asyncio.sleep(1)
            tick += 1
        await self.shutdown()

    async def shutdown(self):
        logger.info("orchestrator.shutdown.start")
        self.log_activity("Shutting down...")
        self.state = SystemState.SHUTDOWN

        for task in self._background_tasks:
            task.cancel()
        await asyncio.gather(*self._background_tasks, return_exceptions=True)

        for name in ("audio_player", "streaming_player", "vector", "graph", "metadata"):
            comp = self.components.get(name)
            if comp and hasattr(comp, "close"):
                try:
                    comp.close()
                except Exception:
                    pass
            if comp and hasattr(comp, "stop"):
                try:
                    comp.stop()
                except Exception:
                    pass

        if "model_registry" in self.components:
            self.components["model_registry"].unload_all()

        logger.info("orchestrator.shutdown.complete")
        self.log_activity("Shutdown complete")

    def handle_signal(self, sig):
        logger.info("orchestrator.signal", signal=sig)
        asyncio.create_task(self.shutdown())

    async def _scheduler_loop(self):
        scheduler = self.components.get("scheduler")
        if not scheduler:
            return
        while self.state != SystemState.SHUTDOWN:
            ctx = self._build_context()
            self.log_activity("Scheduler tick — running due tasks")
            await scheduler.run(ctx)
            self.log_activity("Scheduler tick complete")
            await asyncio.sleep(15)

    async def _run_dashboard(self, dashboard):
        try:
            await asyncio.get_event_loop().run_in_executor(None, dashboard.run)
        except asyncio.CancelledError:
            logger.info("orchestrator.dashboard.cancelled")
        except Exception as e:
            logger.warning("orchestrator.dashboard.error", error=str(e))

    async def _health_check(self):
        while self.state != SystemState.SHUTDOWN:
            state = self.state.value
            logger.debug("orchestrator.health", state=state, components=list(self.components.keys()))
            await asyncio.sleep(self.config.daemon.health_check_interval)

    async def _run_analysis_pipeline(self, context):
        # Wait for concurrent ingestion to populate state
        for _ in range(10):
            if context.state.get("documents"):
                break
            await asyncio.sleep(3)
        doc_count = len(context.state.get("documents", []))
        self.log_activity(f"Analysis pipeline starting ({doc_count} documents in state)...")
        agents = [
            ("claim_extractor", "Extracting claims from documents"),
            ("entity_extractor", "Extracting named entities"),
            ("event_clustering", "Clustering events"),
            ("contradiction_detector", "Detecting contradictions"),
            ("narrative_analyzer", "Analyzing narrative drift"),
            ("framing_analyzer", "Analyzing political framing"),
            ("source_reliability", "Evaluating source reliability"),
            ("graph_updater", "Updating temporal graph"),
        ]
        for agent_name, description in agents:
            self.log_activity(f"→ {description}...")
            await self._run_agent(agent_name)(context)
        self.log_activity("Analysis pipeline complete")

    def _run_agent(self, name: str):
        agent = self.components.get("agents", {}).get(name)
        if not agent:
            self.log_activity(f"Agent '{name}' not registered", level="warn")
            logger.warning("orchestrator.agent.missing", name=name)
            return lambda ctx: None
        async def run(ctx):
            try:
                self.log_activity(f"Running agent: {name}")
                result = await agent.run(ctx)
                if not result.success:
                    self.log_activity(f"Agent '{name}' failed: {result.error}", level="error")
                    logger.warning("orchestrator.agent.failed", name=name, error=result.error)
                else:
                    metrics_str = ", ".join(f"{k}={v}" for k, v in (result.metrics or {}).items())
                    self.log_activity(f"Agent '{name}' complete ({metrics_str})" if metrics_str else f"Agent '{name}' complete")
            except Exception as e:
                self.log_activity(f"Agent '{name}' crashed: {e}", level="error")
                logger.error("orchestrator.agent.crash", name=name, error=str(e))
        return run

    def _build_context(self):
        from src.agents.base import AgentContext
        from pathlib import Path
        ctx = AgentContext(
            trace_id=f"t{int(time.time())}",
            config=self.config.model_dump(),
            state=self._shared_state,
            models=self.components.get("model_registry"),
            graph=self.components.get("graph"),
            vector=self.components.get("vector"),
            metadata=self.components.get("metadata"),
            logger=logger,
        )
        # Add audio components to state for audio_producer
        ctx.state["tts"] = self.components.get("tts")
        ctx.state["audio_cache"] = self.components.get("audio_cache")
        ctx.state["audio_queue"] = self.components.get("audio_queue")
        ctx.state["audio_stitcher"] = self.components.get("audio_stitcher")
        ctx.state["streaming_queue"] = self.components.get("streaming_queue")
        ctx.state["audio_dir"] = Path(self.config.system.data_dir).expanduser() / "audio"
        return ctx


from src.agents.scheduler_daemon import ScheduledTask