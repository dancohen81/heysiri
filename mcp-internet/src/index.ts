#!/usr/bin/env node
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';

interface FetchUrlArgs {
  url: string;
}

const isValidFetchUrlArgs = (args: any): args is FetchUrlArgs =>
  typeof args === 'object' && args !== null && typeof args.url === 'string';

class InternetMcpServer {
  private server: Server;
  private axiosInstance;

  constructor() {
    this.server = new Server(
      {
        name: 'internet-mcp-server',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.axiosInstance = axios.create({});

    this.setupToolHandlers();
    
    // Error handling
    this.server.onerror = (error) => console.error('[MCP Error]', error);
    process.on('SIGINT', async () => {
      await this.server.close();
      process.exit(0);
    });
  }

  private setupToolHandlers() {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => ({
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
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      if (request.params.name !== 'fetch_url') {
        throw new McpError(
          ErrorCode.MethodNotFound,
          `Unknown tool: ${request.params.name}`
        );
      }

      if (!isValidFetchUrlArgs(request.params.arguments)) {
        throw new McpError(
          ErrorCode.InvalidParams,
          'Invalid fetch_url arguments'
        );
      }

      const url = request.params.arguments.url;

      try {
        const response = await this.axiosInstance.get(url);

        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      } catch (error) {
        if (error && typeof error === 'object' && 'isAxiosError' in error && error.isAxiosError) {
          return {
            content: [
              {
                type: 'text',
                text: `Error fetching URL: ${
                  (error as any).response?.data.message ?? (error as any).message
                }`,
              },
            ],
            isError: true,
          };
        }
        throw error;
      }
    });
  }

  async run() {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('Internet MCP server running on stdio');
  }
}

const server = new InternetMcpServer();
server.run().catch(console.error);
