#!/usr/bin/env node
"use strict";
var __awaiter = (this && this.__awaiter) || function (thisArg, _arguments, P, generator) {
    function adopt(value) { return value instanceof P ? value : new P(function (resolve) { resolve(value); }); }
    return new (P || (P = Promise))(function (resolve, reject) {
        function fulfilled(value) { try { step(generator.next(value)); } catch (e) { reject(e); } }
        function rejected(value) { try { step(generator["throw"](value)); } catch (e) { reject(e); } }
        function step(result) { result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected); }
        step((generator = generator.apply(thisArg, _arguments || [])).next());
    });
};
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const index_js_1 = require("@modelcontextprotocol/sdk/server/index.js");
const stdio_js_1 = require("@modelcontextprotocol/sdk/server/stdio.js");
const types_js_1 = require("@modelcontextprotocol/sdk/types.js");
const axios_1 = __importDefault(require("axios"));
const isValidFetchUrlArgs = (args) => typeof args === 'object' && args !== null && typeof args.url === 'string';
class InternetMcpServer {
    constructor() {
        this.server = new index_js_1.Server({
            name: 'internet-mcp-server',
            version: '0.1.0',
        }, {
            capabilities: {
                tools: {},
            },
        });
        this.axiosInstance = axios_1.default.create();
        this.setupToolHandlers();
        // Error handling
        this.server.onerror = (error) => console.error('[MCP Error]', error);
        process.on('SIGINT', () => __awaiter(this, void 0, void 0, function* () {
            yield this.server.close();
            process.exit(0);
        }));
    }
    setupToolHandlers() {
        this.server.setRequestHandler(types_js_1.ListToolsRequestSchema, () => __awaiter(this, void 0, void 0, function* () {
            return ({
                tools: [
                    {
                        name: 'fetch_url',
                        description: 'Fetches content from a given URL',
                        inputSchema: {
                            type: 'object',
                            properties: {
                                url: {
                                    type: 'string',
                                    description: 'The URL to fetch',
                                },
                            },
                            required: ['url'],
                        },
                    },
                ],
            });
        }));
        this.server.setRequestHandler(types_js_1.CallToolRequestSchema, (request) => __awaiter(this, void 0, void 0, function* () {
            var _a, _b;
            if (request.params.name !== 'fetch_url') {
                throw new types_js_1.McpError(types_js_1.ErrorCode.MethodNotFound, `Unknown tool: ${request.params.name}`);
            }
            if (!isValidFetchUrlArgs(request.params.arguments)) {
                throw new types_js_1.McpError(types_js_1.ErrorCode.InvalidParams, 'Invalid fetch_url arguments');
            }
            const url = request.params.arguments.url;
            try {
                const response = yield this.axiosInstance.get(url);
                return {
                    content: [
                        {
                            type: 'text',
                            text: JSON.stringify(response.data, null, 2),
                        },
                    ],
                };
            }
            catch (error) {
                if (axios_1.default.isAxiosError(error)) {
                    return {
                        content: [
                            {
                                type: 'text',
                                text: `Error fetching URL: ${(_b = (_a = error.response) === null || _a === void 0 ? void 0 : _a.data.message) !== null && _b !== void 0 ? _b : error.message}`,
                            },
                        ],
                        isError: true,
                    };
                }
                throw error;
            }
        }));
    }
    run() {
        return __awaiter(this, void 0, void 0, function* () {
            const transport = new stdio_js_1.StdioServerTransport();
            yield this.server.connect(transport);
            console.error('Internet MCP server running on stdio');
        });
    }
}
const server = new InternetMcpServer();
server.run().catch(console.error);
