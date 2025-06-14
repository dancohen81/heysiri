import json
import subprocess
import asyncio
import threading
from typing import Dict, Any, Optional
import uuid
import os

class MCPClient:
    def __init__(self, server_path: str, allowed_dirs: list):
        """
        MCP Client für stdio-basierte Kommunikation
        
        Args:
            server_path: Pfad zum MCP Server (node dist/index.js)  
            allowed_dirs: Liste der erlaubten Verzeichnisse
        """
        self.server_path = server_path
        self.allowed_dirs = allowed_dirs
        self.process = None
        self.request_id = 0
        self.pending_requests = {}
        self.tools = {}
        self.initialized = False
        self.file_write_history = [] # Track file write operations
        
    async def start(self):
        """Startet den MCP Server Prozess"""
        try:
            # Prüfe ob Node.js und Server vorhanden sind
            if not os.path.exists(self.server_path):
                raise Exception(f"MCP Server nicht gefunden: {self.server_path}")
            
            cmd = ["node", self.server_path] + self.allowed_dirs
            print(f"🔧 Starte MCP Server: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,  
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                cwd=os.path.dirname(self.server_path),
                encoding='utf-8' # Specify UTF-8 encoding for stdout/stderr
            )
            
            # Prüfe ob Prozess erfolgreich gestartet
            await asyncio.sleep(0.2)
            if self.process.poll() is not None:
                stderr = self.process.stderr.read()
                raise Exception(f"MCP Server Startup fehlgeschlagen: {stderr}")
                
            # Reader Thread für Antworten starten
            self.reader_thread = threading.Thread(target=self._read_responses, daemon=True)
            self.reader_thread.start()
            
            # Initialisierung des MCP Servers
            await self._initialize()
            
            print("✅ MCP Client erfolgreich gestartet")
            return True
            
        except Exception as e:
            print(f"❌ MCP Client Start fehlgeschlagen: {e}")
            return False
        
    async def _initialize(self):
        """Initialisiert die MCP Verbindung"""
        try:
            # 1. Initialize Request
            init_request = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize", 
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "clientInfo": {
                        "name": "voice-chat-app",
                        "version": "1.0.0"
                    }
                }
            }
            
            response = await self._send_request(init_request)
            if not response or "error" in response:
                raise Exception(f"Initialize fehlgeschlagen: {response}")
                
            print("✅ MCP Server initialisiert")
            
            # 2. Tools laden
            await self._load_tools()
            self.initialized = True
            
        except Exception as e:
            print(f"❌ MCP Initialisierung fehlgeschlagen: {e}")
            raise
            
    async def _load_tools(self):
        """Lädt verfügbare Tools vom MCP Server"""
        try:
            tools_request = {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {}
            }
            
            response = await self._send_request(tools_request)
            if response and "result" in response:
                for tool in response["result"].get("tools", []):
                    self.tools[tool["name"]] = tool
                    print(f"  📁 Tool geladen: {tool['name']}")
            else:
                print("⚠️ Keine Tools vom MCP Server erhalten")
                
        except Exception as e:
            print(f"❌ Fehler beim Laden der Tools: {e}")
    
    def _next_id(self):
        """Generiert eine neue Request ID"""
        self.request_id += 1
        return self.request_id
        
    async def _send_request(self, request: Dict[Any, Any]) -> Optional[Dict[Any, Any]]:
        """Sendet eine JSON-RPC Anfrage an den MCP Server"""
        if not self.process or self.process.poll() is not None:
            raise Exception("MCP Server nicht verfügbar")
            
        request_json = json.dumps(request) + "\n"
        
        # Request in pending requests speichern
        req_id = request["id"]
        future = asyncio.Future()
        self.pending_requests[req_id] = future
        
        try:
            self.process.stdin.write(request_json)
            self.process.stdin.flush()
            
            # Auf Antwort warten (mit Timeout)
            response = await asyncio.wait_for(future, timeout=10.0)
            return response
            
        except asyncio.TimeoutError:
            print(f"❌ Timeout für Request {req_id}")
            if req_id in self.pending_requests:
                del self.pending_requests[req_id]
            return None
        except Exception as e:
            print(f"❌ Fehler beim Senden: {e}")
            if req_id in self.pending_requests:
                del self.pending_requests[req_id]
            return None
    
    def _read_responses(self):
        """Liest kontinuierlich Antworten vom MCP Server"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                    
                if line.strip():  # Ignoriere leere Zeilen
                    response = json.loads(line.strip())
                    
                    # Response zu wartendem Request zuordnen
                    if "id" in response and response["id"] in self.pending_requests:
                        future = self.pending_requests.pop(response["id"])
                        if not future.done():
                            future.set_result(response)
                            
            except json.JSONDecodeError as e:
                print(f"❌ JSON Parse Fehler: {e}, Line: {line}")
                continue
            except Exception as e:
                print(f"❌ Fehler beim Lesen: {e}")
                break
                
        print("🔌 MCP Reader Thread beendet")
    
    async def execute_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Führt einen Tool-Aufruf aus
        
        Args:
            tool_name: Name des Tools
            arguments: Tool-Argumente
            
        Returns:
            Tool-Ergebnis
        """
        if not self.initialized:
            return {"error": "MCP Client nicht initialisiert"}
            
        if tool_name not in self.tools:
            return {"error": f"Tool '{tool_name}' nicht verfügbar. Verfügbare Tools: {list(self.tools.keys())}"}
            
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        try:
            response = await self._send_request(request)
            
            if response and "result" in response:
                return response["result"]
            else:
                error_msg = response.get("error", {}).get("message", "Unbekannter Fehler") if response else "Keine Antwort"
                tool_result = {"error": f"Tool-Ausführung fehlgeschlagen: {error_msg}"}
            
            # Track file write operations
            file_write_tools = ["write_to_file", "apply_diff", "insert_content", "search_and_replace"]
            if tool_name in file_write_tools:
                self.file_write_history.append({
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "success": "error" not in tool_result,
                    "result": tool_result
                })
            
            return tool_result
                
        except Exception as e:
            # Track file write operations even if an exception occurs
            file_write_tools = ["write_to_file", "apply_diff", "insert_content", "search_and_replace"]
            if tool_name in file_write_tools:
                self.file_write_history.append({
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "success": False,
                    "result": {"error": str(e)}
                })
            return {"error": f"Fehler bei Tool-Ausführung: {e}"}
    
    def get_tools_for_claude(self) -> list:
        """
        Konvertiert MCP Tools zu Claude API Format
        
        Returns:
            Liste von Tools für Claude API
        """
        claude_tools = []
        
        for tool_name, tool_info in self.tools.items():
            claude_tool = {
                "name": tool_name,
                "description": tool_info.get("description", f"MCP Tool: {tool_name}"),
                "input_schema": tool_info.get("inputSchema", {"type": "object", "properties": {}})
            }
            # Ensure input_schema is a valid JSON schema structure
            if not isinstance(claude_tool["input_schema"], dict):
                print(f"⚠️ Ungültiges input_schema für Tool '{tool_name}'. Setze auf Standard.")
                claude_tool["input_schema"] = {"type": "object", "properties": {}}
            
            claude_tools.append(claude_tool)
            
        return claude_tools
        
    def get_file_write_history(self) -> list:
        """Gibt die Historie der Dateischreiboperationen zurück"""
        return self.file_write_history
    
    def is_ready(self) -> bool:
        """Prüft ob MCP Client bereit ist"""
        return self.initialized and self.process and self.process.poll() is None
    
    def stop(self):
        """Stoppt den MCP Server"""
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            finally:
                self.process = None
        self.initialized = False
        print("🔌 MCP Client gestoppt")


from src.config import MCP_SERVER_CONFIG, MCP_ALLOWED_DIRS, save_mcp_config

class MCPManager:
    """Manager für mehrere MCP Clients mit einfacher API"""
    
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {} # Store clients by a unique identifier (e.g., server ID)
        self.ready = False
        
    async def setup(self):
        """Initialisiert alle MCP Clients basierend auf MCP_SERVER_CONFIG"""
        # Stoppe alle bestehenden Clients, bevor neue gestartet werden
        self.stop() 
        self.clients = {} 
        all_ready = True
        
        for server_id, config in MCP_SERVER_CONFIG.items():
            server_path = config.get("path")
            enabled = config.get("enabled", False) # Default to disabled if not specified
            
            if not server_path:
                print(f"⚠️ MCP Server '{server_id}' hat keinen Pfad konfiguriert. Überspringe.")
                continue

            if not enabled:
                print(f"ℹ️ MCP Server '{server_id}' ist deaktiviert. Überspringe Start.")
                continue

            try:
                client = MCPClient(server_path, MCP_ALLOWED_DIRS) # Pass global allowed_dirs for now
                
                print(f"🔧 Versuche, MCP Client für {server_id} zu starten...")
                client_started = await client.start()
                
                if client_started:
                    self.clients[server_id] = client
                    print(f"✅ MCP Client für {server_id} erfolgreich gestartet.")
                else:
                    print(f"❌ MCP Client für {server_id} konnte nicht gestartet werden.")
                    all_ready = False
            except Exception as e:
                print(f"❌ Fehler beim Starten des MCP Clients für {server_id}: {e}")
                all_ready = False
                
        self.ready = all_ready and bool(self.clients) # Ensure at least one client is ready
        return self.ready

    def get_mcp_status(self) -> Dict[str, Dict[str, Any]]:
        """Gibt den Status aller MCP Server zurück (aktiv/inaktiv, enabled/disabled)"""
        status = {}
        for server_id, config in MCP_SERVER_CONFIG.items():
            is_running = self.clients.get(server_id) and self.clients[server_id].is_ready()
            status[server_id] = {
                "path": config.get("path"),
                "enabled": config.get("enabled", False),
                "running": is_running
            }
        return status

    async def set_mcp_enabled(self, server_id: str, enabled: bool) -> bool:
        """
        Setzt den 'enabled' Status eines MCP Servers und versucht, ihn neu zu starten/stoppen.
        """
        if server_id not in MCP_SERVER_CONFIG:
            print(f"❌ MCP Server '{server_id}' nicht gefunden.")
            return False
        
        current_config = MCP_SERVER_CONFIG[server_id]
        if current_config["enabled"] == enabled:
            print(f"ℹ️ MCP Server '{server_id}' ist bereits im gewünschten Zustand (enabled={enabled}).")
            return True

        current_config["enabled"] = enabled
        save_mcp_config({server_id: current_config}) # Update in-memory config

        # Attempt to restart/stop the specific client or the whole manager
        # For simplicity and robustness, we'll re-setup all clients.
        # In a more complex app, you might try to stop/start only the affected client.
        print(f"🔄 Re-initialisiere MCP Manager nach Änderung für '{server_id}'.")
        await self.setup() # Re-setup all clients based on new config
        return True
    
    def get_tools_for_claude(self) -> list:
        """Aggregiert Tools von allen aktiven MCP Clients für Claude"""
        all_claude_tools = []
        for client in self.clients.values():
            if client.is_ready():
                all_claude_tools.extend(client.get_tools_for_claude())
        return all_claude_tools
    
    async def execute_tool(self, tool_name: str, arguments: dict):
        """Führt Tool über den passenden MCP Client aus"""
        if not self.ready:
            return {"error": "MCP Manager nicht bereit"}
            
        for client in self.clients.values():
            if tool_name in client.tools:
                print(f"DEBUG: Führe Tool '{tool_name}' über Client '{os.path.basename(os.path.dirname(client.server_path))}' aus.")
                return await client.execute_tool_call(tool_name, arguments)
        
        return {"error": f"Tool '{tool_name}' nicht in einem der verbundenen MCP Server gefunden."}
    
    def is_ready(self) -> bool:
        """Prüft ob alle MCP Clients bereit sind"""
        if not self.clients:
            return False
        return all(client.is_ready() for client in self.clients.values())
    
    def stop(self):
        """Stoppt alle MCP Clients"""
        for client in self.clients.values():
            client.stop()
        self.clients = {}
        self.ready = False
