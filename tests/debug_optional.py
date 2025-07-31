"""Debug Optional resolution issue."""

import sys

from whiskey import Whiskey

sys.path.append(".")
from tests.test_optional_consistency import Cache, Database, ServiceWithOptionalDep


def debug_optional_resolution():
    app = Whiskey()

    # Register required and optional dependencies
    app.singleton(Database)
    app.singleton(Cache)
    app.component(ServiceWithOptionalDep)

    print("=== Registry Contents ===")
    for descriptor in app.container.registry.list_all():
        print(f"Key: {descriptor.key}, Type: {descriptor.component_type}")

    print("\n=== Cache registration check ===")
    print(f"Registry has Cache: {app.container.registry.has(Cache)}")
    print(f"Registry has 'Cache': {app.container.registry.has('Cache')}")

    print("\n=== Injection Analysis ===")
    results = app.container.analyzer.analyze_callable(ServiceWithOptionalDep.__init__)
    for param_name, result in results.items():
        print(f"{param_name}: {result}")
        if result.inner_type:
            print(f"  Inner type: {result.inner_type}")
            print(f"  Registry has inner type: {app.container.registry.has(result.inner_type)}")

    print("\n=== Resolution ===")
    service = app.resolve(ServiceWithOptionalDep)
    print(f"Service: {service}")
    print(f"Service.db: {service.db}")
    print(f"Service.cache: {service.cache}")


if __name__ == "__main__":
    debug_optional_resolution()
