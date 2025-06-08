#!/usr/bin/env node
import dotenv from 'dotenv';
dotenv.config({ path: '../../.env' }); // Load environment variables from .env file
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ErrorCode,
  ListToolsRequestSchema,
  McpError,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';
import nodemailer from 'nodemailer';

interface FetchUrlArgs {
  url: string;
}

const isValidFetchUrlArgs = (args: any): args is FetchUrlArgs =>
  typeof args === 'object' && args !== null && typeof args.url === 'string';

interface SendEmailArgs {
  to: string;
  subject: string;
  text: string;
  html?: string;
  smtpHost?: string; // Optional, can be read from env
  smtpPort?: number; // Optional, can be read from env
  smtpUser?: string; // Optional, can be read from env
  smtpPass?: string; // Optional, can be read from env
}

const isValidSendEmailArgs = (args: any): args is SendEmailArgs =>
  typeof args === 'object' &&
  args !== null &&
  typeof args.to === 'string' &&
  typeof args.subject === 'string' &&
  typeof args.text === 'string'; // smtpHost, smtpPort, smtpUser, smtpPass are now optional

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
        {
          name: 'send_email',
          description: 'Sends an email using SMTP',
          inputSchema: {
            type: 'object',
            properties: {
              to: { type: 'string', description: 'Recipient email address' },
              subject: { type: 'string', description: 'Email subject' },
              text: { type: 'string', description: 'Plain text body of the email' },
              html: { type: 'string', description: 'HTML body of the email (optional)' },
              smtpHost: { type: 'string', description: 'SMTP server host (optional, reads from env if not provided)' },
              smtpPort: { type: 'number', description: 'SMTP server port (optional, reads from env if not provided)' },
              smtpUser: { type: 'string', description: 'SMTP username (optional, reads from env if not provided)' },
              smtpPass: { type: 'string', description: 'SMTP password (optional, reads from env if not provided)' },
            },
            required: ['to', 'subject', 'text'],
          },
        },
      ],
    }));

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      if (request.params.name === 'fetch_url') {
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
      } else if (request.params.name === 'send_email') {
        if (!isValidSendEmailArgs(request.params.arguments)) {
          throw new McpError(
            ErrorCode.InvalidParams,
            'Invalid send_email arguments'
          );
        }

        const { to, subject, text, html } = request.params.arguments;

        const finalSmtpHost = request.params.arguments.smtpHost || process.env.SMTP_HOST;
        const finalSmtpPort = request.params.arguments.smtpPort || parseInt(process.env.SMTP_PORT || '587');
        const finalSmtpUser = request.params.arguments.smtpUser || process.env.SMTP_USER;
        const finalSmtpPass = request.params.arguments.smtpPass || process.env.SMTP_PASS;

        if (!finalSmtpHost || !finalSmtpUser || !finalSmtpPass) {
          throw new McpError(
            ErrorCode.InvalidParams,
            'SMTP host, user, or password not provided and not found in environment variables.'
          );
        }

        try {
          const transporter = nodemailer.createTransport({
            host: finalSmtpHost,
            port: finalSmtpPort,
            secure: finalSmtpPort === 465, // true for 465, false for other ports
            auth: {
              user: finalSmtpUser,
              pass: finalSmtpPass,
            },
          });

          const info = await transporter.sendMail({
            from: finalSmtpUser, // sender address
            to, // list of receivers
            subject, // Subject line
            text, // plain text body
            html, // html body
          });

          return {
            content: [
              {
                type: 'text',
                text: `Email sent: ${info.messageId}`,
              },
            ],
          };
        } catch (error: any) {
          return {
            content: [
              {
                type: 'text',
                text: `Error sending email: ${error.message}`,
              },
            ],
            isError: true,
          };
        }
      } else {
        throw new McpError(
          ErrorCode.MethodNotFound,
          `Unknown tool: ${request.params.name}`
        );
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
