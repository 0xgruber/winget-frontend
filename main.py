"""
Winget TUI Frontend - A Text User Interface for Windows Package Manager
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    TabbedContent,
    TabPane,
    Tabs,
    DataTable,
    Input,
    Button,
    Label,
    Footer,
    Header,
    Static,
    RichLog,
)
from textual.widgets._footer import FooterKey  # For custom Footer compose
from textual.worker import Worker, get_current_worker
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual import on
from textual.coordinate import Coordinate
from textual.events import Click, Focus
from typing import List, Optional, Tuple

from winget_client import WingetClient, Package


class AppBindingsFooter(Footer):
    """Custom Footer that always shows App bindings, regardless of focused widget."""
    
    def _get_app_bindings(self) -> list[Binding]:
        """Get current App bindings."""
        app = self.app
        if app and hasattr(app, 'BINDINGS'):
            bindings = getattr(app, 'BINDINGS', None)
            if bindings:
                return list(bindings)
        return []
    
    def compose(self) -> ComposeResult:
        """Override compose to use App's BINDINGS instead of screen.active_bindings."""
        bindings = self._get_app_bindings()
        
        # Yield FooterKey widgets for each binding (mimicking parent's compose)
        for binding in bindings:
            key = binding.key if hasattr(binding, 'key') else str(binding)
            key_display = self.app.get_key_display(binding) if hasattr(self.app, 'get_key_display') else key
            desc = binding.description if hasattr(binding, 'description') and binding.description else binding.action
            action = binding.action if hasattr(binding, 'action') else ""
            # Don't use data_bind when manually remounting - just yield FooterKey directly
            yield FooterKey(key, key_display, desc, action)


class WingetApp(App):
    """Main application class for the Winget TUI."""
    
    @property
    def active_bindings(self) -> list[Binding]:
        """Override active_bindings to return only self.BINDINGS, preventing accumulation."""
        if hasattr(self, 'BINDINGS'):
            return list(self.BINDINGS)
        return super().active_bindings if hasattr(super(), 'active_bindings') else []
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    TabbedContent {
        height: 100%;
    }
    
    TabPane {
        padding: 1;
    }
    
    DataTable {
        height: 1fr;
    }
    
    .search-container {
        height: 3;
        margin-bottom: 1;
    }
    
    .button-container {
        height: 3;
        margin-top: 1;
    }
    
    Button.install {
        background: $success;
        margin-right: 1;
    }
    
    Button.uninstall {
        background: $error;
        margin-right: 1;
    }
    
    Button.upgrade {
        background: $warning;
        margin-right: 1;
    }
    
    Button.upgrade-all {
        background: #FF8C00;
    }
    
    /* Override primary variant to match other buttons */
    Button.-primary {
        margin-right: 1;
    }
    
    RichLog {
        height: 8;
        border: solid $primary;
    }
    
    /* Add spacing between footer keys */
    FooterKey {
        padding-right: 2;
    }
    """
    
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("r", "refresh", "Refresh", priority=True),
    ]
    
    def __init__(self):
        super().__init__()
        self.winget_client = WingetClient()
        self.log_widget: Optional[RichLog] = None
        self.uninstall_btn: Optional[Button] = None
        self.upgrade_btn: Optional[Button] = None
        self.selected_package_id: Optional[str] = None
        self.selected_update_package_id: Optional[str] = None
        self.search_input: Optional[Input] = None
        self.installed_fetched: bool = False
        self.updates_fetched: bool = False
        self.updates_log_widget: Optional[RichLog] = None
        self.installed_table: Optional[DataTable] = None
        self.installed_search_input: Optional[Input] = None
        self.updates_search_input: Optional[Input] = None
        self.upgrade_all_btn: Optional[Button] = None
        self.installed_packages_data: List[Package] = []
        self.updates_data: List[Package] = []
        self.last_installed_cursor_row: Optional[int] = None
        self.last_updates_cursor_row: Optional[int] = None
        self.browse_log_widget: Optional[RichLog] = None
        self.install_user_btn: Optional[Button] = None
        self.install_system_btn: Optional[Button] = None
        self.selected_search_package_id: Optional[str] = None
        self.last_search_cursor_row: Optional[int] = None
    
    def check_table_selections(self) -> None:
        """Check DataTable cursor positions and update button states."""
        try:
            # Check installed table
            try:
                installed_table = self.query_one("#installed-table", DataTable)
                current_row = installed_table.cursor_row
                if current_row != self.last_installed_cursor_row:
                    self.last_installed_cursor_row = current_row
                    if current_row is not None:
                        try:
                            try:
                                row_data = installed_table.get_row(current_row)
                                if row_data and len(row_data) >= 2:
                                    package_id = str(row_data[1])
                                    self.selected_package_id = package_id
                                    if self.uninstall_btn:
                                        self.uninstall_btn.disabled = False
                            except Exception:
                                try:
                                    coord = installed_table.cursor_coordinate
                                    if coord:
                                        id_coord = Coordinate(row=coord.row, column=1)
                                        cell_value = installed_table.get_cell_at(id_coord)
                                        if cell_value:
                                            package_id = str(cell_value)
                                            self.selected_package_id = package_id
                                            if self.uninstall_btn:
                                                self.uninstall_btn.disabled = False
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
            
            # Check search table (Browse & Install)
            try:
                search_table = self.query_one("#search-table", DataTable)
                current_row = search_table.cursor_row
                if current_row != self.last_search_cursor_row:
                    self.last_search_cursor_row = current_row
                    if current_row is not None:
                        try:
                            try:
                                row_data = search_table.get_row(current_row)
                                if row_data and len(row_data) >= 2:
                                    package_id = str(row_data[1])
                                    self.selected_search_package_id = package_id
                                    if self.install_user_btn:
                                        self.install_user_btn.disabled = False
                                    if self.install_system_btn:
                                        self.install_system_btn.disabled = False
                            except Exception:
                                try:
                                    coord = search_table.cursor_coordinate
                                    if coord:
                                        id_coord = Coordinate(row=coord.row, column=1)
                                        cell_value = search_table.get_cell_at(id_coord)
                                        if cell_value:
                                            package_id = str(cell_value)
                                            self.selected_search_package_id = package_id
                                            if self.install_user_btn:
                                                self.install_user_btn.disabled = False
                                            if self.install_system_btn:
                                                self.install_system_btn.disabled = False
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
            
            # Check updates table
            try:
                updates_table = self.query_one("#updates-table", DataTable)
                current_row = updates_table.cursor_row
                if current_row != self.last_updates_cursor_row:
                    self.last_updates_cursor_row = current_row
                    if current_row is not None:
                        try:
                            try:
                                row_data = updates_table.get_row(current_row)
                                if row_data and len(row_data) >= 2:
                                    package_id = str(row_data[1])
                                    self.selected_update_package_id = package_id
                                    if self.upgrade_btn:
                                        self.upgrade_btn.disabled = False
                            except Exception:
                                try:
                                    coord = updates_table.cursor_coordinate
                                    if coord:
                                        id_coord = Coordinate(row=coord.row, column=1)
                                        cell_value = updates_table.get_cell_at(id_coord)
                                        if cell_value:
                                            package_id = str(cell_value)
                                            self.selected_update_package_id = package_id
                                            if self.upgrade_btn:
                                                self.upgrade_btn.disabled = False
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass
        except Exception:
            pass
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=True)
        with TabbedContent():
            with TabPane("Browse & Install", id="browse-tab"):
                pass
            with TabPane("Installed Packages", id="installed-tab"):
                pass
            with TabPane("Updates", id="updates-tab"):
                pass
        yield AppBindingsFooter()
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.setup_installed_tab()
        self.setup_browse_tab()
        self.setup_updates_tab()
        self.set_interval(0.1, self.check_table_selections)
    
    def setup_installed_tab(self) -> None:
        """Set up the Installed Packages tab."""
        try:
            installed_tab = self.query_one("#installed-tab", TabPane)
        except Exception:
            return
        
        container = Vertical(id="installed-container")
        log_widget = RichLog(id="installed-log", markup=True)
        self.log_widget = log_widget
        
        search_input = Input(placeholder="Search installed packages...", id="installed-search-input")
        self.installed_search_input = search_input
        search_container = Horizontal(classes="search-container")
        
        table = DataTable(id="installed-table", zebra_stripes=True)
        table.add_column("Name", key="name")
        table.add_column("ID", key="id")
        table.add_column("Version", key="version")
        table.add_column("Source", key="source")
        self.installed_table = table
        
        refresh_btn = Button("Refresh", id="refresh-installed", variant="primary")
        uninstall_btn = Button("Uninstall", id="uninstall-btn", classes="uninstall", disabled=True)
        self.uninstall_btn = uninstall_btn
        
        button_container = Horizontal(classes="button-container")
        installed_tab.mount(container)
        container.mount(search_container, table, button_container, log_widget)
        
        try:
            search_container.mount(search_input)
        except Exception:
            def mount_search():
                try:
                    search_container.mount(search_input)
                except Exception:
                    pass
            self.set_timer(0.01, mount_search)
        
        try:
            button_container.mount(refresh_btn, uninstall_btn)
        except Exception:
            def mount_buttons():
                try:
                    button_container.mount(refresh_btn, uninstall_btn)
                except Exception:
                    pass
            self.set_timer(0.01, mount_buttons)
        
        self.fetch_installed_packages()
    
    def setup_browse_tab(self) -> None:
        """Set up the Browse & Install tab."""
        browse_tab = self.query_one("#browse-tab", TabPane)
        
        container = Vertical(id="browse-container")
        search_input = Input(placeholder="Search for packages...", id="search-input")
        search_button = Button("Search", id="search-btn", variant="primary")
        search_container = Horizontal(classes="search-container")
        
        log_widget = RichLog(id="browse-log", markup=True)
        self.browse_log_widget = log_widget
        
        table = DataTable(id="search-table", zebra_stripes=True)
        table.add_column("Name", key="name")
        table.add_column("ID", key="id")
        table.add_column("Version", key="version")
        table.add_column("Source", key="source")
        
        install_user_btn = Button("Install (User)", id="install-user-btn", classes="install", disabled=True)
        install_system_btn = Button("Install (System)", id="install-system-btn", classes="install", disabled=True)
        
        self.search_input = search_input
        self.search_table = table
        self.install_user_btn = install_user_btn
        self.install_system_btn = install_system_btn
        
        button_container = Horizontal(classes="button-container")
        browse_tab.mount(container)
        container.mount(search_container, table, button_container, log_widget)
        
        try:
            search_container.mount(search_input, search_button)
            button_container.mount(install_user_btn, install_system_btn)
        except Exception:
            def mount_browse_widgets():
                try:
                    search_container.mount(search_input, search_button)
                    button_container.mount(install_user_btn, install_system_btn)
                except Exception:
                    pass
            self.set_timer(0.01, mount_browse_widgets)
    
    def setup_updates_tab(self) -> None:
        """Set up the Updates tab."""
        try:
            updates_tab = self.query_one("#updates-tab", TabPane)
        except Exception:
            return
        
        container = Vertical(id="updates-container")
        search_input = Input(placeholder="Search updates...", id="updates-search-input")
        self.updates_search_input = search_input
        search_container = Horizontal(classes="search-container")
        
        log_widget = RichLog(id="updates-log", markup=True)
        self.updates_log_widget = log_widget
        
        table = DataTable(id="updates-table", zebra_stripes=True)
        table.add_column("Name", key="name")
        table.add_column("ID", key="id")
        table.add_column("Current Version", key="current_version")
        table.add_column("Available Version", key="available_version")
        table.add_column("Source", key="source")
        self.updates_table = table
        
        check_btn = Button("Refresh", id="check-updates", variant="primary")
        upgrade_btn = Button("Upgrade", id="upgrade-btn", classes="upgrade", disabled=True)
        upgrade_all_btn = Button("Upgrade All", id="upgrade-all-btn", classes="upgrade upgrade-all", disabled=True)
        
        self.upgrade_btn = upgrade_btn
        self.upgrade_all_btn = upgrade_all_btn
        
        button_container = Horizontal(classes="button-container")
        
        try:
            updates_tab.mount(container)
        except Exception:
            return
        
        try:
            container.mount(search_container, table, button_container, log_widget)
        except Exception:
            return
        
        try:
            search_container.mount(search_input)
        except Exception:
            def mount_search():
                try:
                    search_container.mount(search_input)
                except Exception:
                    pass
            self.set_timer(0.01, mount_search)
        
        try:
            button_container.mount(check_btn, upgrade_btn, upgrade_all_btn)
        except Exception:
            def mount_buttons():
                try:
                    button_container.mount(check_btn, upgrade_btn, upgrade_all_btn)
                except Exception:
                    pass
            self.set_timer(0.01, mount_buttons)
        
        if not self.updates_fetched:
            self.fetch_updates()
            self.updates_fetched = True
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "refresh-installed":
            if self.log_widget:
                self.log_widget.write("[yellow]Refreshing installed packages...[/yellow]\n")
            self.fetch_installed_packages()
        elif event.button.id == "search-btn":
            self.perform_search()
        elif event.button.id == "uninstall-btn":
            self.perform_uninstall()
        elif event.button.id == "upgrade-btn":
            self.perform_upgrade()
        elif event.button.id == "check-updates":
            self.action_refresh()
        elif event.button.id == "install-user-btn":
            self.perform_install(user_context=True)
        elif event.button.id == "install-system-btn":
            self.perform_install(user_context=False)
    
    @on(DataTable.HeaderSelected)
    def on_data_table_header_click(self, event: DataTable.HeaderSelected) -> None:
        """Handle clicks on DataTable column headers to enable sorting."""
        table = event.data_table
        column_key_obj = event.column_key
        column_key_value = column_key_obj.value if hasattr(column_key_obj, 'value') else str(column_key_obj)
        
        if column_key_obj:
            try:
                if not hasattr(self, '_table_sort_state'):
                    self._table_sort_state = {}
                
                table_id = table.id if hasattr(table, 'id') else id(table)
                current_sort_info = self._table_sort_state.get(table_id, None)
                reverse = False
                
                if current_sort_info is not None:
                    current_key_value, current_reverse = current_sort_info
                    if current_key_value == column_key_value:
                        reverse = not current_reverse
                    else:
                        reverse = False
                else:
                    reverse = False
                
                table.sort(column_key_obj, reverse=reverse)
                self._table_sort_state[table_id] = (column_key_value, reverse)
            except Exception:
                pass
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission (Enter key)."""
        if event.input.id == "search-input":
            self.perform_search()
        elif event.input.id == "installed-search-input":
            self.filter_installed_table()
        elif event.input.id == "updates-search-input":
            self.filter_updates_table()
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input changes for real-time filtering."""
        if event.input.id == "installed-search-input":
            self.filter_installed_table()
        elif event.input.id == "updates-search-input":
            self.filter_updates_table()
    
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection in data tables."""
        table = event.data_table
        try:
            row_key = event.cursor_row
            row_data = table.get_row(row_key)
            
            if event.data_table.id == "installed-table":
                if row_data and len(row_data) >= 2:
                    package_id = str(row_data[1])
                    self.selected_package_id = package_id
                    if self.uninstall_btn:
                        self.uninstall_btn.disabled = False
            elif event.data_table.id == "updates-table":
                if row_data and len(row_data) >= 2:
                    package_id = str(row_data[1])
                    self.selected_update_package_id = package_id
                    if self.upgrade_btn:
                        self.upgrade_btn.disabled = False
        except Exception:
            if event.data_table.id == "installed-table":
                if self.uninstall_btn:
                    self.uninstall_btn.disabled = True
            elif event.data_table.id == "updates-table":
                if self.upgrade_btn:
                    self.upgrade_btn.disabled = True
    
    def perform_search(self) -> None:
        """Perform package search."""
        if not hasattr(self, 'search_input') or not self.search_input:
            return
        
        query = self.search_input.value.strip()
        if not query:
            return
        
        search_table = self.query_one("#search-table", DataTable)
        search_table.clear()
        
        def do_search() -> Tuple[List[Package], Optional[str]]:
            """Worker function to search packages."""
            worker = get_current_worker()
            if worker.is_cancelled:
                return [], None
            packages, error = self.winget_client.search(query)
            return packages, error
        
        def on_complete(result: Tuple[List[Package], Optional[str]]) -> None:
            """Called when search completes."""
            packages, error = result
            try:
                search_table = self.query_one("#search-table", DataTable)
                if error:
                    search_table.add_row(f"Error: {error}", "", "", "")
                else:
                    search_table.clear()
                    for pkg in packages:
                        search_table.add_row(pkg.name, pkg.id, pkg.version, pkg.source, key=pkg.name)
            except Exception:
                pass
        
        worker = self.run_worker(do_search, thread=True, exclusive=False)
        
        def check_worker_result():
            try:
                if worker.is_finished:
                    result = worker.result
                    on_complete(result)
                else:
                    self.call_after_refresh(check_worker_result)
            except Exception:
                try:
                    self.call_after_refresh(check_worker_result)
                except:
                    pass
        
        self.call_after_refresh(check_worker_result)
    
    def perform_uninstall(self) -> None:
        """Perform package uninstall."""
        if not self.selected_package_id:
            return
        
        package_id = self.selected_package_id
        
        def do_uninstall() -> Tuple[bool, Optional[str]]:
            """Worker function to uninstall package."""
            worker = get_current_worker()
            if worker.is_cancelled:
                return False, "Cancelled"
            success, error = self.winget_client.uninstall(package_id)
            return success, error
        
        def on_complete(result: Tuple[bool, Optional[str]]) -> None:
            """Called when uninstall completes."""
            success, error = result
            if self.log_widget:
                if success:
                    self.log_widget.write(f"[green]Successfully uninstalled {package_id}[/green]\n")
                    self.fetch_installed_packages()
                else:
                    self.log_widget.write(f"[red]Failed to uninstall {package_id}: {error}[/red]\n")
        
        if self.log_widget:
            self.log_widget.write(f"[yellow]Uninstalling {package_id}...[/yellow]\n")
        
        worker = self.run_worker(do_uninstall, thread=True, exclusive=False)
        
        def check_worker_result():
            try:
                if worker.is_finished:
                    result = worker.result
                    on_complete(result)
                else:
                    self.call_after_refresh(check_worker_result)
            except Exception:
                try:
                    self.call_after_refresh(check_worker_result)
                except:
                    pass
        
        self.call_after_refresh(check_worker_result)
    
    def perform_install(self, user_context: bool = False) -> None:
        """Perform package installation."""
        package_id = self.selected_search_package_id
        
        if not package_id:
            return
        
        log_widget = self.browse_log_widget
        
        def do_install() -> Tuple[bool, Optional[str]]:
            """Worker function to install package."""
            worker = get_current_worker()
            if worker.is_cancelled:
                return False, "Cancelled"
            success, error = self.winget_client.install(package_id, user_context=user_context)
            return success, error
        
        def on_complete(result: Tuple[bool, Optional[str]]) -> None:
            """Called when install completes."""
            success, error = result
            context_str = "user" if user_context else "system"
            if log_widget:
                if success:
                    log_widget.write(f"[green]Successfully installed {package_id} ({context_str} context)[/green]\n")
                    if self.install_user_btn:
                        self.install_user_btn.disabled = True
                    if self.install_system_btn:
                        self.install_system_btn.disabled = True
                else:
                    log_widget.write(f"[red]Failed to install {package_id} ({context_str} context): {error}[/red]\n")
        
        if log_widget:
            context_str = "user" if user_context else "system"
            log_widget.write(f"[yellow]Installing {package_id} ({context_str} context)...[/yellow]\n")
        
        worker = self.run_worker(do_install, thread=True, exclusive=False)
        
        def check_worker_result():
            try:
                if worker.is_finished:
                    result = worker.result
                    on_complete(result)
                else:
                    self.call_after_refresh(check_worker_result)
            except Exception:
                try:
                    self.call_after_refresh(check_worker_result)
                except:
                    pass
        
        self.call_after_refresh(check_worker_result)
    
    def perform_upgrade(self) -> None:
        """Perform package upgrade."""
        package_id = self.selected_update_package_id or self.selected_package_id
        
        if not package_id:
            return
        
        log_widget = self.updates_log_widget if self.selected_update_package_id else self.log_widget
        
        def do_upgrade() -> Tuple[bool, Optional[str]]:
            """Worker function to upgrade package."""
            worker = get_current_worker()
            if worker.is_cancelled:
                return False, "Cancelled"
            success, error = self.winget_client.upgrade(package_id)
            return success, error
        
        def on_complete(result: Tuple[bool, Optional[str]]) -> None:
            """Called when upgrade completes."""
            success, error = result
            if log_widget:
                if success:
                    log_widget.write(f"[green]Successfully upgraded {package_id}[/green]\n")
                    if self.selected_update_package_id:
                        self.fetch_updates()
                    else:
                        self.fetch_installed_packages()
                else:
                    log_widget.write(f"[red]Failed to upgrade {package_id}: {error}[/red]\n")
        
        if log_widget:
            log_widget.write(f"[yellow]Upgrading {package_id}...[/yellow]\n")
        
        worker = self.run_worker(do_upgrade, thread=True, exclusive=False)
        
        def check_worker_result():
            try:
                if worker.is_finished:
                    result = worker.result
                    on_complete(result)
                else:
                    self.call_after_refresh(check_worker_result)
            except Exception:
                try:
                    self.call_after_refresh(check_worker_result)
                except:
                    pass
        
        self.call_after_refresh(check_worker_result)
    
    def filter_installed_table(self) -> None:
        """Filter installed packages table based on search input."""
        if not self.installed_search_input or not self.installed_table:
            return
        
        query = self.installed_search_input.value.strip().lower()
        self.installed_table.clear()
        
        if not query:
            for pkg in self.installed_packages_data:
                self.installed_table.add_row(pkg.name, pkg.id, pkg.version, pkg.source)
        else:
            for pkg in self.installed_packages_data:
                if (query in pkg.name.lower() or 
                    query in pkg.id.lower() or 
                    query in pkg.version.lower() or 
                    query in pkg.source.lower()):
                    self.installed_table.add_row(pkg.name, pkg.id, pkg.version, pkg.source)
    
    def filter_updates_table(self) -> None:
        """Filter updates table based on search input."""
        if not self.updates_search_input or not self.updates_table:
            return
        
        query = self.updates_search_input.value.strip().lower()
        self.updates_table.clear()
        
        if not query:
            for pkg in self.updates_data:
                self.updates_table.add_row(pkg.name, pkg.id, pkg.version, pkg.available_version, pkg.source)
        else:
            for pkg in self.updates_data:
                if (query in pkg.name.lower() or 
                    query in pkg.id.lower() or 
                    query in pkg.version.lower() or 
                    query in pkg.available_version.lower() or
                    query in pkg.source.lower()):
                    self.updates_table.add_row(pkg.name, pkg.id, pkg.version, pkg.available_version, pkg.source)
    
    def perform_upgrade_all(self) -> None:
        """Upgrade all packages with available updates."""
        if not self.updates_table or not self.updates_data:
            return
        
        package_ids = [pkg.id for pkg in self.updates_data]
        
        if not package_ids:
            if self.updates_log_widget:
                self.updates_log_widget.write("[yellow]No updates available to upgrade[/yellow]\n")
            return
        
        if self.updates_log_widget:
            self.updates_log_widget.write(f"[yellow]Upgrading {len(package_ids)} packages...[/yellow]\n")
        
        def do_upgrade_all() -> Tuple[int, int, List[str]]:
            """Worker function to upgrade all packages."""
            worker = get_current_worker()
            success_count = 0
            fail_count = 0
            errors = []
            
            for package_id in package_ids:
                if worker.is_cancelled:
                    break
                success, error = self.winget_client.upgrade(package_id)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{package_id}: {error}")
            
            return success_count, fail_count, errors
        
        def on_complete(result: Tuple[int, int, List[str]]) -> None:
            """Called when upgrade all completes."""
            success_count, fail_count, errors = result
            if self.updates_log_widget:
                if success_count > 0:
                    self.updates_log_widget.write(f"[green]Successfully upgraded {success_count} package(s)[/green]\n")
                if fail_count > 0:
                    self.updates_log_widget.write(f"[red]Failed to upgrade {fail_count} package(s)[/red]\n")
                    for error in errors:
                        self.updates_log_widget.write(f"[red]  {error}[/red]\n")
                
                self.fetch_updates()
        
        worker = self.run_worker(do_upgrade_all, thread=True, exclusive=False)
        
        def check_worker_result():
            try:
                if worker.is_finished:
                    result = worker.result
                    on_complete(result)
                else:
                    self.call_after_refresh(check_worker_result)
            except Exception:
                try:
                    self.call_after_refresh(check_worker_result)
                except:
                    pass
        
        self.call_after_refresh(check_worker_result)
    
    def fetch_installed_packages(self) -> None:
        """Fetch installed packages using the WingetClient."""
        def do_fetch() -> Tuple[List[Package], Optional[str]]:
            """Worker function to fetch packages."""
            worker = get_current_worker()
            if worker.is_cancelled:
                return [], None
            packages, error = self.winget_client.list_installed()
            return packages, error
        
        def on_complete(result: Tuple[List[Package], Optional[str]]) -> None:
            """Called when fetch completes."""
            packages, error = result
            
            try:
                if self.log_widget:
                    if error:
                        self.log_widget.write(f"[red]Error: {error}[/red]\n")
                    else:
                        self.log_widget.write(f"[green]Successfully fetched {len(packages)} installed packages[/green]\n")
                
                try:
                    table = self.query_one("#installed-table", DataTable)
                    table.clear()
                    self.installed_packages_data = packages
                    for pkg in packages:
                        table.add_row(pkg.name, pkg.id, pkg.version, pkg.source)
                    if self.installed_search_input and self.installed_search_input.value.strip():
                        self.filter_installed_table()
                except Exception:
                    pass
            except Exception:
                pass
        
        worker = self.run_worker(do_fetch, thread=True, exclusive=False)
        
        def check_worker_result():
            try:
                if worker.is_finished:
                    result = worker.result
                    on_complete(result)
                else:
                    self.call_after_refresh(check_worker_result)
            except Exception:
                try:
                    self.call_after_refresh(check_worker_result)
                except:
                    pass
        
        self.call_after_refresh(check_worker_result)
    
    def fetch_updates(self) -> None:
        """Fetch available updates using the WingetClient."""
        def do_fetch() -> Tuple[List[Package], Optional[str]]:
            """Worker function to fetch updates."""
            worker = get_current_worker()
            if worker.is_cancelled:
                return [], None
            packages, error = self.winget_client.check_for_updates()
            return packages, error
        
        def on_complete(result: Tuple[List[Package], Optional[str]]) -> None:
            """Called when fetch completes."""
            packages, error = result
            
            try:
                if self.updates_log_widget:
                    if error:
                        self.updates_log_widget.write(f"[red]Error: {error}[/red]\n")
                    else:
                        self.updates_log_widget.write(f"[green]Found {len(packages)} available updates[/green]\n")
                
                try:
                    table = self.query_one("#updates-table", DataTable)
                    table.clear()
                    self.updates_data = packages
                    for pkg in packages:
                        table.add_row(pkg.name, pkg.id, pkg.version, pkg.available_version, pkg.source)
                    if self.upgrade_all_btn:
                        self.upgrade_all_btn.disabled = len(packages) == 0
                    if self.updates_search_input and self.updates_search_input.value.strip():
                        self.filter_updates_table()
                except Exception:
                    pass
            except Exception:
                pass
        
        worker = self.run_worker(do_fetch, thread=True, exclusive=False)
        
        def check_worker_result():
            try:
                if worker.is_finished:
                    result = worker.result
                    on_complete(result)
                else:
                    self.call_after_refresh(check_worker_result)
            except Exception:
                try:
                    self.call_after_refresh(check_worker_result)
                except:
                    pass
        
        self.call_after_refresh(check_worker_result)
    
    def action_refresh(self) -> None:
        """Refresh the current view."""
        tabbed_content = self.query_one(TabbedContent)
        try:
            active_tab_pane = tabbed_content.active_pane
            if active_tab_pane and active_tab_pane.id == "installed-tab":
                if self.log_widget:
                    self.log_widget.write("[yellow]Refreshing installed packages...[/yellow]\n")
                self.fetch_installed_packages()
            elif active_tab_pane and active_tab_pane.id == "updates-tab":
                if self.updates_log_widget:
                    self.updates_log_widget.write("[yellow]Checking for updates...[/yellow]\n")
                self.fetch_updates()
        except:
            if self.log_widget:
                self.log_widget.write("[yellow]Refreshing installed packages...[/yellow]\n")
            self.fetch_installed_packages()
    
    @on(TabbedContent.TabActivated)
    def on_tab_changed(self, event: TabbedContent.TabActivated) -> None:
        """Called when the active tab changes."""
        self.update_tab_bindings()
        self.refresh_footer_with_app_bindings()
    
    def update_tab_bindings(self) -> None:
        """Update bindings based on the active tab."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            active_pane = tabbed_content.active_pane
            active_tab_id = active_pane.id if active_pane else None
            
            new_bindings = [
                Binding("q", "quit", "Quit", priority=True),
                Binding("r", "refresh", "Refresh", priority=True),
                Binding("n", "next_tab", "Next Tab", priority=True),
                Binding("p", "previous_tab", "Previous Tab", priority=True),
            ]
            
            if active_tab_id == "browse-tab":
                new_bindings.extend([
                    Binding("i", "install_user", "Install User", priority=True),
                    Binding("I", "install_system", "Install System", priority=True),
                    Binding("s", "focus_search", "Search", priority=True),
                ])
            elif active_tab_id == "installed-tab":
                new_bindings.extend([
                    Binding("x", "uninstall", "Uninstall", priority=True),
                    Binding("s", "focus_search", "Search", priority=True),
                ])
            elif active_tab_id == "updates-tab":
                new_bindings.extend([
                    Binding("u", "upgrade", "Upgrade", priority=True),
                    Binding("a", "upgrade_all", "Upgrade All", priority=True),
                    Binding("s", "focus_search", "Search", priority=True),
                ])
            
            self.BINDINGS = new_bindings
            
            for binding in new_bindings:
                try:
                    desc = binding.description if hasattr(binding, 'description') and binding.description else ""
                    self.bind(binding.key, binding.action, description=desc)
                except Exception:
                    pass
            
            try:
                footer = self.query_one(AppBindingsFooter)
                footer.remove_children()
                for binding in self.BINDINGS:
                    key = binding.key if hasattr(binding, 'key') else str(binding)
                    key_display = self.get_key_display(binding) if hasattr(self, 'get_key_display') else key
                    desc = binding.description if hasattr(binding, 'description') and binding.description else binding.action
                    action = binding.action if hasattr(binding, 'action') else ""
                    footer.mount(FooterKey(key, key_display, desc, action))
            except Exception:
                pass
        except Exception:
            pass
    
    def refresh_footer_with_app_bindings(self) -> None:
        """Force footer to show App-level bindings, not focused widget bindings."""
        try:
            footer = self.query_one(Footer)
            footer.refresh()
        except Exception:
            pass
    
    @on(Focus)
    def on_focus(self, event: Focus) -> None:
        """Handle focus changes to ensure footer always shows App bindings."""
        self.call_after_refresh(self.refresh_footer_with_app_bindings)
    
    def action_focus_search(self) -> None:
        """Focus the search input in the active tab."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            active_pane = tabbed_content.active_pane
            active_tab_id = active_pane.id if active_pane else None
            
            if active_tab_id == "browse-tab" and self.search_input:
                self.search_input.focus()
            elif active_tab_id == "installed-tab" and self.installed_search_input:
                self.installed_search_input.focus()
            elif active_tab_id == "updates-tab" and self.updates_search_input:
                self.updates_search_input.focus()
        except Exception:
            pass
    
    def action_search(self) -> None:
        """Perform search in Browse & Install tab."""
        self.perform_search()
    
    def action_install_user(self) -> None:
        """Install package in user context."""
        if self.install_user_btn and not self.install_user_btn.disabled:
            self.perform_install(user_context=True)
    
    def action_install_system(self) -> None:
        """Install package in system context."""
        if self.install_system_btn and not self.install_system_btn.disabled:
            self.perform_install(user_context=False)
    
    def action_uninstall(self) -> None:
        """Uninstall selected package."""
        if self.uninstall_btn and not self.uninstall_btn.disabled:
            self.perform_uninstall()
    
    def action_upgrade(self) -> None:
        """Upgrade selected package."""
        if self.upgrade_btn and not self.upgrade_btn.disabled:
            self.perform_upgrade()
    
    def action_upgrade_all(self) -> None:
        """Upgrade all packages."""
        if self.upgrade_all_btn and not self.upgrade_all_btn.disabled:
            self.perform_upgrade_all()
    
    def action_next_tab(self) -> None:
        """Switch to the next tab."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            tabs = tabbed_content.query_one(Tabs)
            tabs.action_next_tab()
        except Exception:
            pass
    
    def action_previous_tab(self) -> None:
        """Switch to the previous tab."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            tabs = tabbed_content.query_one(Tabs)
            tabs.action_previous_tab()
        except Exception:
            pass
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()


if __name__ == "__main__":
    app = WingetApp()
    app.run()
