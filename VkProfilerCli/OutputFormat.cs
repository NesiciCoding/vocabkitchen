using System;

namespace VkProfilerCli
{
    public enum OutputFormat
    {
        Json,
        Pretty,
    }

    public static class OutputFormatResolver
    {
        /// <summary>
        /// Resolves the effective output format. An explicit <c>--format</c> value wins;
        /// otherwise the format auto-detects from whether stdout is redirected (a pipe/file
        /// gets machine-readable JSON, an interactive terminal gets the pretty view).
        /// </summary>
        /// <param name="explicitFormat">The value passed to <c>--format</c>, or null for auto.</param>
        /// <param name="isOutputRedirected"><see cref="Console.IsOutputRedirected"/>.</param>
        public static bool TryResolve(string explicitFormat, bool isOutputRedirected, out OutputFormat format, out string error)
        {
            error = null;

            if (string.IsNullOrWhiteSpace(explicitFormat) || explicitFormat.Equals("auto", StringComparison.OrdinalIgnoreCase))
            {
                format = isOutputRedirected ? OutputFormat.Json : OutputFormat.Pretty;
                return true;
            }

            switch (explicitFormat.Trim().ToLowerInvariant())
            {
                case "json":
                    format = OutputFormat.Json;
                    return true;
                case "pretty":
                case "text":
                    format = OutputFormat.Pretty;
                    return true;
                default:
                    format = OutputFormat.Json;
                    error = $"Unknown format '{explicitFormat}'. Valid formats: auto, json, pretty.";
                    return false;
            }
        }
    }
}
