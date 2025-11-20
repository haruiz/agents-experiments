import {
  CopilotRuntime,
  ExperimentalEmptyAdapter,
  copilotRuntimeNextJSAppRouterEndpoint,
} from "@copilotkit/runtime";
import { HttpAgent } from "@ag-ui/client";
import { NextRequest } from "next/server";

// Create a service adapter for the CopilotKit runtime
const serviceAdapter = new ExperimentalEmptyAdapter();
// Create the main CopilotRuntime instance that manages communication between the frontend and backend agents
const runtime = new CopilotRuntime({
// Define the agents that will be available to the frontend
    agents: {
// Configure the ADK agent connection
    weather_agent: new HttpAgent({
      // Specify the URL where the ADK agent is running
      url: "http://localhost:8000/",
    })
},
});
// Export the POST handler for the API route
export const POST = async (req: NextRequest) => {
// Create the request handler using CopilotKit's Next.js helper
const { handleRequest } = copilotRuntimeNextJSAppRouterEndpoint({
    runtime, // The CopilotRuntime instance we configured
    serviceAdapter, // The service adapter for agent coordination
    endpoint: "/api/copilotkit", // The endpoint path (matches this file's location)
});
return handleRequest(req);
};