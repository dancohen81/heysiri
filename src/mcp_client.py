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
                cwd=os.path.dirname(self.server_path)
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
                return {"error": f"Tool-Ausführung fehlgeschlagen: {error_msg}"}
                
        except Exception as e:
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
                "input_schema": tool_info.get("inputSchema", {
                    "type": "object",
                    "properties": {}
                })
            }
            claude_tools.append(claude_tool)
            
        return claude_tools
    
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


class MCPManager:
    """Manager für MCP Client mit einfacher API"""
    
    def __init__(self):
        self.client = None
        self.ready = False
        
    async def setup(self, server_path: str = None, allowed_dirs: list = None):
        """Initialisiert MCP Client mit Standard-Werten"""
        if server_path is None:
            server_path = "D:/Users/stefa/servers/src/filesystem/dist/index.js"
        if allowed_dirs is None:
            allowed_dirs = ["D:/Users/stefa/heysiri"]
            
        try:
            self.client = MCPClient(server_path, allowed_dirs)
            self.ready = await self.client.start()
            return self.ready
        except Exception as e:
            print(f"❌ MCP Setup fehlgeschlagen: {e}")
            self.ready = False
            return False
    
    def get_tools_for_claude(self) -> list:
        """Gibt Tools für Claude zurück"""
        if self.ready and self.client:
            return self.client.get_tools_for_claude()
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict):
        """Führt Tool aus"""
        if not self.ready or not self.client:
            return {"error": "MCP nicht bereit"}
        return await self.client.execute_tool_call(tool_name, arguments)
    
    def is_ready(self) -> bool:
        """Prüft MCP Status"""
        return self.ready and self.client and self.client.is_ready()
    
    def stop(self):
        """Stoppt MCP"""
        if self.client:
            self.client.stop()
        self.ready = False