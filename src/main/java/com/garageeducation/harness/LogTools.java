package com.garageeducation.harness;

import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Component;

/**
 * Log tools the model can call.
 *
 * <p>The model sees only the tool name, the {@link Tool} description, and each
 * {@link ToolParam} description. It never sees the method body.
 */
@Component
public class LogTools {

    /**
     * Counts error log events for one service.
     *
     * <p>The data is fake. The {@code checkout} service returns 412. Every other service returns 3.
     *
     * @param service the service name, for example {@code checkout}
     * @param minutes the look-back window in minutes, from 1 to 1440; the fake data ignores it
     * @return the number of error events
     */
    @Tool(description = "Count error log events for one service in the last N minutes. Use this to check for a current error spike.")
    public int countErrors(@ToolParam(description = "Service name, for example checkout") String service,
                           @ToolParam(description = "Look-back window in minutes, from 1 to 1440") int minutes) {
        return "checkout".equals(service) ? 412 : 3; // fake data
    }
}
