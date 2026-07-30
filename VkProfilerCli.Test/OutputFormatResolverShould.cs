using VkProfilerCli;
using Xunit;

namespace VkProfilerCli.Test
{
    public class OutputFormatResolverShould
    {
        [Theory]
        [InlineData(null, true, OutputFormat.Json)]      // redirected -> machine JSON (the skill)
        [InlineData(null, false, OutputFormat.Pretty)]   // interactive terminal -> human view
        [InlineData("auto", true, OutputFormat.Json)]
        [InlineData("auto", false, OutputFormat.Pretty)]
        public void Auto_detect_from_redirection(string arg, bool redirected, OutputFormat expected)
        {
            Assert.True(OutputFormatResolver.TryResolve(arg, redirected, out var format, out _));
            Assert.Equal(expected, format);
        }

        [Theory]
        [InlineData("json", OutputFormat.Json)]
        [InlineData("JSON", OutputFormat.Json)]
        [InlineData("pretty", OutputFormat.Pretty)]
        [InlineData("text", OutputFormat.Pretty)]
        public void Honour_explicit_format_over_redirection(string arg, OutputFormat expected)
        {
            // isOutputRedirected deliberately opposite to what the arg asks for.
            bool redirected = expected == OutputFormat.Pretty;
            Assert.True(OutputFormatResolver.TryResolve(arg, redirected, out var format, out _));
            Assert.Equal(expected, format);
        }

        [Fact]
        public void Reject_unknown_format()
        {
            Assert.False(OutputFormatResolver.TryResolve("fancy", false, out _, out var error));
            Assert.Contains("Unknown format", error);
        }
    }
}
