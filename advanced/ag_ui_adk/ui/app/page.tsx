"use client";

import React, {useState} from "react";
import "@copilotkit/react-ui/styles.css";
import "./style.css";

// CopilotKit core
import {
    useFrontendTool,
    useRenderToolCall,
} from "@copilotkit/react-core";
import {CopilotChat} from "@copilotkit/react-ui";

// Weather card component + types
import WeatherCard, {
    getThemeColor,
    WeatherToolResult,
    WeatherMCPToolResult,
} from "@/app/components/WeatherCard";
import GoogleMap from "@/app/components/GoogleMap";

/* ------------------------------------------------------------------------------------------------
 * TYPE GUARDS & PARSERS
 * ----------------------------------------------------------------------------------------------*/

/**
 * Narrow a result to WeatherMCPToolResult by checking for the "content" field.
 */
function isWeatherMCPToolResult(
    result: WeatherToolResult | WeatherMCPToolResult
): result is WeatherMCPToolResult {
    return "content" in result;
}

/**
 * Convert MCP tool output into a WeatherToolResult if it contains valid JSON payload.
 */
function mcpToWeatherResult(
    result: WeatherMCPToolResult
): WeatherToolResult | null {
    if (!result.content || result.content.length === 0) return null;

    const text = result.content[0].text?.trim();
    if (!text) return null;

    try {
        const parsed = JSON.parse(text);

        // Validate minimal expected structure
        if (
            typeof parsed.temperature === "number" &&
            typeof parsed.conditions === "string"
        ) {
            return parsed as WeatherToolResult;
        }

        return null;
    } catch {
        // JSON parse error
        return null;
    }
}

/* ------------------------------------------------------------------------------------------------
 * CHAT COMPONENT
 * ----------------------------------------------------------------------------------------------*/

const Chat = () => {
    // Dynamic background controlled by tool usage
    const [background, setBackground] = useState<string>(
        "--copilot-kit-background-color"
    );

    // Dynamic suggestions for weather queries
    const locations = ["San Francisco", "New York", "Tokyo"];

    const suggestions = [
        {
            title: "Change background",
            message: "Change the background to a nice gradient.",
        },
        ...locations.map((location) => ({
            title: `Get weather in ${location}`,
            message: `What is the weather in ${location}?`,
        })),
        ...locations.map((location) => ({
            title: `Show me ${location} on a map`,
            message: `Get me the location of ${location}.`,
        }))
    ];

    /* --------------------------------------------------------------------------------------------
     * CHANGE BACKGROUND TOOL
     * This tool allows the LLM to set the chat background.
     * ------------------------------------------------------------------------------------------*/
    useFrontendTool({
        name: "change_background",
        description:
            "Change the chat's background using any CSS background value (color, gradient, etc.).",
        parameters: [
            {
                name: "background",
                type: "string",
                description: "CSS background definition (colors, gradients, etc).",
            },
        ],

        // The tool handler executes when the LLM calls this tool.
        handler: ({background}) => {
            setBackground(background);

            return {
                status: "success",
                message: `Background changed to ${background}`,
            };
        },
    });

    /* --------------------------------------------------------------------------------------------
    * RENDER PLACE LOCATION TOOL CALL
    * This visually renders the result of the get_place_location tool.
    * ------------------------------------------------------------------------------------------
     */

    useRenderToolCall({
        name: "get_place_location",
        description: "get the latitude and longitude of a place given its name.",
        available: "disabled",
        parameters: [{name: "place_name", type: "string", required: true}],
        render: ({args, status, result}) => {
            if (status === "inProgress") {
                return (
                    <div className="bg-[#667eea] text-white p-4 rounded-lg max-w-md">
                        <span className="animate-spin">⚙️ Retrieving location...</span>
                    </div>
                );
            }
            if (status === "complete" && result) {
                const {result: coords} = result;
                return <GoogleMap lat={coords?.latitude} lng={coords?.longitude}/>;
            }
            return null;
        }
    })

    /* --------------------------------------------------------------------------------------------
     * RENDER WEATHER TOOL CALL
     * This visually renders the result of the get_weather tool.
     * ------------------------------------------------------------------------------------------*/
    useRenderToolCall({
        name: "get_weather",
        description: "Get the current weather for a specified location.",
        available: "disabled", // Using MCP or manually invoking elsewhere
        parameters: [{name: "location", type: "string", required: true}],
        render: ({args, status, result}) => {
            /* STATUS: inProgress --------------------------------------------------*/
            if (status === "inProgress") {
                return (
                    <div className="bg-[#667eea] text-white p-4 rounded-lg max-w-md">
                        <span className="animate-spin">⚙️ Retrieving weather...</span>
                    </div>
                );
            }

            /* STATUS: complete ----------------------------------------------------*/
            if (status === "complete" && result) {
                console.log("Raw Weather Result:", result);

                let weatherResult: WeatherToolResult | null = result;

                // If MCP-style result, convert it
                if (isWeatherMCPToolResult(result)) {
                    weatherResult = mcpToWeatherResult(result);
                }

                if (!weatherResult) {
                    return (
                        <div className="bg-red-300 text-red-900 p-4 rounded-lg max-w-md">
                            <strong>Weather parse error:</strong> Could not interpret tool
                            result.
                        </div>
                    );
                }

                // Choose color based on weather conditions
                const themeColor = getThemeColor(weatherResult.conditions);

                return (
                    <WeatherCard
                        location={args.location}
                        themeColor={themeColor}
                        result={weatherResult}
                        status={status || "complete"}
                    />
                );
            }

            return null;
        },
    });

    /* --------------------------------------------------------------------------------------------
     * MAIN UI RENDERING
     * ------------------------------------------------------------------------------------------*/
    return (
        <div
            className="flex justify-center items-center h-full w-full"
            data-testid="background-container"
            style={{background}}
        >
            <div className="h-full w-full md:w-8/10 md:h-8/10 rounded-lg">
                <CopilotChat
                    className="h-full rounded-2xl max-w-6xl mx-auto"
                    labels={{initial: "Hi, I'm an agent. Want to chat?"}}
                    suggestions={suggestions}
                />
            </div>
        </div>
    );
};

/* ------------------------------------------------------------------------------------------------
 * HOME PAGE WRAPPER
 * ----------------------------------------------------------------------------------------------*/

const HomePage = () => {
    return (
        <main className="h-screen w-screen">
            <Chat/>
        </main>
    );
};

export default HomePage;
