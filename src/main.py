"""mDNS (Multicast DNS) service."""
import json
import logging
import time
import sched
import signal
import atexit
import socket
from pathlib import Path
from dataclasses import dataclass, field, asdict
from zeroconf import ServiceInfo, Zeroconf

logger = logging.getLogger(__name__)


@dataclass
class MDNSConfig:
    """Configuration for the mDNS service."""
    type: str = "_http._tcp.local."
    name: str = ""
    port: int = 8080
    properties: dict = field(default_factory=dict)
    timeout: float = 60


class MDNSManager:
    """Manages mDNS service registration and updates."""

    def __init__(self, info: ServiceInfo, sched_timeout: float) -> None:
        """Initialize the mDNS service.

        Args:
            info (ServiceInfo): 
                Zeroconf ServiceInfo object containing service details.
            sched_timeout (float): 
                Timeout in seconds for the scheduler.
        """
        self.info = info
        self.sched_timeout = sched_timeout
        self.zeroconf = Zeroconf()
        self.service_sched = sched.scheduler(time.time, time.sleep)

    def register(self) -> None:
        """Registers the mDNS service."""
        self.zeroconf.register_service(self.info)

    def unregister(self) -> None:
        """Unregister the mDNS service."""
        self.zeroconf.unregister_service(self.info)

    def close(self) -> None:
        """Closes the mDNS service and performs cleanup."""
        self.zeroconf.close()

    def _sched_handler(self) -> None:
        """Scheduler for managing periodic service registration."""
        logger.info("Update mDNS registration")
        self.unregister()
        self.register()
        self.service_sched.enter(self.sched_timeout, 1, self._sched_handler)

    def run_sched(self) -> None:
        """Starts the scheduler."""
        logger.info("Starting mDNS service scheduler")
        self.service_sched.enter(1, 0, self._sched_handler)
        self.service_sched.run()


def load_config(config_path: Path) -> MDNSConfig:
    """Loads service configuration from a JSON file.

    Args:
        config_path (Path): Path to the configuration file.

    Returns:
        MDNSConfig: The loaded configuration.
    """
    try:
        config_data = config_path.read_text("utf-8")
        config = MDNSConfig(**json.loads(config_data))
    except FileNotFoundError:
        config = MDNSConfig()
        config_data = json.dumps(asdict(config), indent=4)
        config_path.write_text(config_data, "utf-8")
        logger.warning("Config file not found. Created default config.")
    except (TypeError, json.JSONDecodeError):
        config = MDNSConfig()
        logger.warning("Invalid JSON in config file. Using defaults.")
    return config


def main() -> None:
    """Configuration loading and service setup."""
    log_format = "%(asctime)s [%(levelname)s] %(module)s: %(message)s"
    logging.basicConfig(level=logging.INFO, format=log_format)
    config_path = Path(__file__).parent/"config.json"
    mdns_config = load_config(config_path)

    service_name = mdns_config.name
    if not mdns_config.name:
        service_name = socket.gethostname()

    service_info = ServiceInfo(
        type_=mdns_config.type,
        name=f"{service_name}.{mdns_config.type}",
        port=mdns_config.port,
        properties=mdns_config.properties,
        server=f"{socket.gethostname()}.local.",
    )

    mdns_service = MDNSManager(service_info, mdns_config.timeout)
    atexit.register(mdns_service.close)
    signal.signal(signal.SIGTERM, lambda signum, frame: mdns_service.close())
    mdns_service.run_sched()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
