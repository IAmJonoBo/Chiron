"""Tests for chiron.plugins module - plugin system and registry."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from chiron.plugins import (
    ChironPlugin,
    PluginMetadata,
    PluginRegistry,
    discover_plugins,
    get_plugin,
    initialize_plugins,
    list_plugins,
    register_plugin,
)


class TestPluginMetadata:
    """Tests for PluginMetadata dataclass."""

    def test_plugin_metadata_creation(self) -> None:
        """Test creating plugin metadata."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
        )
        assert metadata.name == "test-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "A test plugin"
        assert metadata.author == ""

    def test_plugin_metadata_with_author(self) -> None:
        """Test creating plugin metadata with author."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
            author="Test Author",
        )
        assert metadata.author == "Test Author"

    def test_plugin_metadata_frozen(self) -> None:
        """Test that plugin metadata is immutable."""
        metadata = PluginMetadata(
            name="test-plugin",
            version="1.0.0",
            description="A test plugin",
        )
        with pytest.raises(AttributeError):
            metadata.name = "new-name"  # type: ignore


class MockPlugin(ChironPlugin):
    """Mock plugin for testing."""

    def __init__(
        self,
        name: str = "mock-plugin",
        version: str = "1.0.0",
        description: str = "Mock plugin",
    ):
        self._name = name
        self._version = version
        self._description = description

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name=self._name,
            version=self._version,
            description=self._description,
        )

    def initialize(self, config: dict) -> None:
        """Initialize the plugin."""
        pass


class TestChironPlugin:
    """Tests for ChironPlugin abstract base class."""

    def test_cannot_instantiate_abstract_plugin(self) -> None:
        """Test that ChironPlugin cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ChironPlugin()  # type: ignore

    def test_mock_plugin_metadata(self) -> None:
        """Test mock plugin metadata property."""
        plugin = MockPlugin()
        metadata = plugin.metadata
        assert metadata.name == "mock-plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Mock plugin"

    def test_mock_plugin_initialize(self) -> None:
        """Test mock plugin initialize method."""
        plugin = MockPlugin()
        config = {"setting": "value"}
        plugin.initialize(config)  # Should not raise


class TestPluginRegistry:
    """Tests for PluginRegistry class."""

    def setup_method(self) -> None:
        """Reset the registry before each test."""
        # Get the module-level registry and clear it
        from chiron import plugins

        plugins._registry._plugins.clear()
        plugins._registry._initialized.clear()

    def test_registry_singleton(self) -> None:
        """Test that PluginRegistry instances are independent."""
        registry1 = PluginRegistry()
        registry2 = PluginRegistry()
        # These are different instances (not singleton by default)
        assert registry1 is not registry2

    def test_register_plugin(self) -> None:
        """Test registering a plugin."""
        plugin = MockPlugin()
        registry = PluginRegistry()
        registry.register(plugin)
        assert registry.get("mock-plugin") == plugin

    def test_register_duplicate_plugin(self) -> None:
        """Test that registering a duplicate plugin raises ValueError."""
        plugin1 = MockPlugin()
        plugin2 = MockPlugin()
        registry = PluginRegistry()

        registry.register(plugin1)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(plugin2)

    def test_get_plugin_exists(self) -> None:
        """Test getting a registered plugin."""
        plugin = MockPlugin()
        registry = PluginRegistry()
        registry.register(plugin)
        result = registry.get("mock-plugin")
        assert result == plugin

    def test_get_plugin_not_found(self) -> None:
        """Test getting a non-existent plugin."""
        registry = PluginRegistry()
        result = registry.get("nonexistent-plugin")
        assert result is None

    def test_list_plugins_empty(self) -> None:
        """Test listing plugins when registry is empty."""
        registry = PluginRegistry()
        plugins = registry.list_plugins()
        assert plugins == []

    def test_list_plugins_with_plugins(self) -> None:
        """Test listing plugins with registered plugins."""
        plugin1 = MockPlugin("plugin1", "1.0.0", "First plugin")
        plugin2 = MockPlugin("plugin2", "2.0.0", "Second plugin")
        registry = PluginRegistry()
        registry.register(plugin1)
        registry.register(plugin2)

        plugins = registry.list_plugins()
        assert len(plugins) == 2
        assert plugins[0].name == "plugin1"
        assert plugins[1].name == "plugin2"


class TestModuleLevelFunctions:
    """Tests for module-level plugin functions."""

    def setup_method(self) -> None:
        """Reset the registry before each test."""
        from chiron import plugins

        plugins._registry._plugins.clear()
        plugins._registry._initialized.clear()

    def test_register_plugin_function(self) -> None:
        """Test register_plugin module function."""
        plugin = MockPlugin()
        register_plugin(plugin)
        assert get_plugin("mock-plugin") == plugin

    def test_get_plugin_function(self) -> None:
        """Test get_plugin module function."""
        plugin = MockPlugin()
        register_plugin(plugin)
        result = get_plugin("mock-plugin")
        assert result == plugin

    def test_get_plugin_function_not_found(self) -> None:
        """Test get_plugin module function with non-existent plugin."""
        result = get_plugin("nonexistent")
        assert result is None

    def test_list_plugins_function(self) -> None:
        """Test list_plugins module function."""
        plugin = MockPlugin()
        register_plugin(plugin)
        plugins = list_plugins()
        assert len(plugins) == 1
        assert plugins[0].name == "mock-plugin"


class TestDiscoverPlugins:
    """Tests for plugin discovery."""

    def test_discover_plugins_no_entry_points(self) -> None:
        """Test discovering plugins when no entry points exist."""
        with patch("chiron.plugins.importlib.metadata.entry_points") as mock_ep:
            mock_ep.return_value = []
            plugins = discover_plugins()
            assert plugins == []

    def test_discover_plugins_with_entry_points(self) -> None:
        """Test discovering plugins from entry points."""
        mock_entry_point = Mock()
        mock_entry_point.name = "test-plugin"
        mock_entry_point.load.return_value = MockPlugin

        with patch("chiron.plugins.importlib.metadata.entry_points") as mock_ep:
            mock_ep.return_value = [mock_entry_point]
            plugins = discover_plugins()
            assert len(plugins) == 1
            assert isinstance(plugins[0], MockPlugin)

    def test_discover_plugins_load_error(self) -> None:
        """Test discovering plugins with load error."""
        mock_entry_point = Mock()
        mock_entry_point.name = "bad-plugin"
        mock_entry_point.load.side_effect = ImportError("Cannot load plugin")

        with patch("chiron.plugins.importlib.metadata.entry_points") as mock_ep:
            mock_ep.return_value = [mock_entry_point]
            with patch("chiron.plugins.logger") as mock_logger:
                plugins = discover_plugins()
                assert plugins == []
                mock_logger.error.assert_called_once()

    def test_discover_plugins_instantiation_error(self) -> None:
        """Test discovering plugins that fail to instantiate."""

        class BadPlugin:
            """A class that raises an error on instantiation."""

            def __init__(self):
                raise RuntimeError("Cannot instantiate")

        mock_entry_point = Mock()
        mock_entry_point.name = "bad-plugin"
        mock_entry_point.load.return_value = BadPlugin

        with patch("chiron.plugins.importlib.metadata.entry_points") as mock_ep:
            mock_ep.return_value = [mock_entry_point]
            with patch("chiron.plugins.logger") as mock_logger:
                plugins = discover_plugins()
                # Should catch the RuntimeError and log error, returning empty list
                assert plugins == []
                mock_logger.error.assert_called()


class TestInitializePlugins:
    """Tests for plugin initialization."""

    def setup_method(self) -> None:
        """Reset the registry before each test."""
        from chiron import plugins

        plugins._registry._plugins.clear()
        plugins._registry._initialized.clear()

    def test_initialize_plugins_empty_config(self) -> None:
        """Test initializing plugins with empty config."""
        plugin = MockPlugin()
        register_plugin(plugin)
        initialize_plugins({})  # Should not raise

    def test_initialize_plugins_with_config(self) -> None:
        """Test initializing plugins with configuration."""
        plugin = MockPlugin()
        register_plugin(plugin)

        config = {"mock-plugin": {"setting": "value"}}
        with patch.object(plugin, "initialize") as mock_init:
            initialize_plugins(config)
            mock_init.assert_called_once_with({"setting": "value"})

    def test_initialize_plugins_no_matching_config(self) -> None:
        """Test initializing plugins when no config matches."""
        plugin = MockPlugin()
        register_plugin(plugin)

        config = {"other-plugin": {"setting": "value"}}
        with patch.object(plugin, "initialize") as mock_init:
            initialize_plugins(config)
            # Plugin should still be called with empty config
            mock_init.assert_called_once_with({})

    def test_initialize_plugins_error_handling(self) -> None:
        """Test error handling during plugin initialization."""
        plugin = MockPlugin()
        register_plugin(plugin)

        config = {"mock-plugin": {"setting": "value"}}
        with patch.object(
            plugin, "initialize", side_effect=ValueError("Init error")
        ) as mock_init:
            with patch("chiron.plugins.logger") as mock_logger:
                initialize_plugins(config)
                mock_init.assert_called_once()
                mock_logger.error.assert_called_once()
