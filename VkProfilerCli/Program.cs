using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using Spectre.Console;
using VkCore.Models.Profiler;
using VkInfrastructure.Profilers;
using VkProfilerCli.Rendering;
using VkProfilerCli.TextExtraction;

namespace VkProfilerCli
{
    public class Program
    {
        public static int Main(string[] args)
        {
            string profilerType = "all";
            string text = null;
            string filePath = null;
            string formatArg = null;

            for (int i = 0; i < args.Length; i++)
            {
                switch (args[i])
                {
                    case "--type":
                        if (!TryTakeValue(args, ref i, "--type", out profilerType))
                            return 1;
                        profilerType = profilerType.ToLowerInvariant();
                        break;
                    case "--file":
                        if (!TryTakeValue(args, ref i, "--file", out filePath))
                            return 1;
                        break;
                    case "--text":
                        if (!TryTakeValue(args, ref i, "--text", out text))
                            return 1;
                        break;
                    case "--format":
                        if (!TryTakeValue(args, ref i, "--format", out formatArg))
                            return 1;
                        break;
                    default:
                        text ??= args[i];
                        break;
                }
            }

            string sourceLabel = null;
            if (filePath != null)
            {
                try
                {
                    text = new DocumentReader().Read(filePath);
                    sourceLabel = Path.GetFileName(filePath);
                }
                catch (DocumentReadException ex)
                {
                    Console.Error.WriteLine(ex.Message);
                    return 1;
                }
            }

            if (text == null && Console.IsInputRedirected)
                text = Console.In.ReadToEnd();

            if (string.IsNullOrWhiteSpace(text))
            {
                Console.Error.WriteLine("Usage: vkprofiler [--type cefr|awl|nawl|all] [--format auto|json|pretty] [--text \"...\" | --file path{.txt|.md|.docx|.pdf} | < stdin]");
                return 1;
            }

            if (!OutputFormatResolver.TryResolve(formatArg, Console.IsOutputRedirected, out var format, out var formatError))
            {
                Console.Error.WriteLine(formatError);
                return 1;
            }

            var profilers = new Dictionary<string, VkCore.Interfaces.IProfiler>
            {
                ["cefr"] = new CefrProfiler(),
                ["awl"] = new AwlProfiler(),
                ["nawl"] = new NawlProfiler(),
            };

            var typesToRun = profilerType == "all"
                ? profilers.Keys.ToList()
                : profilerType.Split(',').Select(t => t.Trim()).ToList();

            var results = new Dictionary<string, ProfilerResult>();
            foreach (var type in typesToRun)
            {
                if (!profilers.TryGetValue(type, out var profiler))
                {
                    Console.Error.WriteLine($"Unknown profiler type '{type}'. Valid types: cefr, awl, nawl, all.");
                    return 1;
                }

                results[type] = profiler.Profile(text);
            }

            if (format == OutputFormat.Pretty)
                new PrettyRenderer(AnsiConsole.Console).Render(sourceLabel, results);
            else
                Console.WriteLine(BuildJson(results));

            return 0;
        }

        private static string BuildJson(Dictionary<string, ProfilerResult> results)
        {
            int? totalWordCount = null;
            var output = new Dictionary<string, object>();

            foreach (var kvp in results)
            {
                totalWordCount ??= kvp.Value.TotalWordCount;

                var levels = new Dictionary<string, object>();
                foreach (var level in kvp.Value.TableResult)
                {
                    levels[level.Key] = new
                    {
                        percentage = level.Value.Percentage,
                        wordCount = level.Value.Rows?.Sum(r => r.Occurrences) ?? 0,
                        words = level.Value.Rows?
                            .OrderByDescending(r => r.Occurrences)
                            .Select(r => new { word = StripHtml(r.RowHtml), occurrences = r.Occurrences })
                    };
                }

                output[kvp.Key] = levels;
            }

            var final = new
            {
                totalWordCount,
                results = output
            };

            return JsonSerializer.Serialize(final, new JsonSerializerOptions
            {
                WriteIndented = true,
                Encoder = System.Text.Encodings.Web.JavaScriptEncoder.UnsafeRelaxedJsonEscaping
            });
        }

        private static bool TryTakeValue(string[] args, ref int i, string flag, out string value)
        {
            if (i + 1 >= args.Length)
            {
                Console.Error.WriteLine($"Missing value for {flag}.");
                value = null;
                return false;
            }

            value = args[++i];
            return true;
        }

        private static string StripHtml(string rowHtml)
        {
            if (string.IsNullOrEmpty(rowHtml))
                return rowHtml;

            int gt = rowHtml.IndexOf('>');
            int lt = rowHtml.LastIndexOf('<');
            if (gt >= 0 && lt > gt)
                return rowHtml.Substring(gt + 1, lt - gt - 1);

            return rowHtml;
        }
    }
}
