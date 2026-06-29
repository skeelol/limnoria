# Limnoria Recap Plugin

A Limnoria IRC bot plugin that summarizes channel chat activity over a specified time period using Claude Haiku API.

## Features

- **Efficient Token Usage**: Uses Claude 3.5 Haiku for minimal API costs
- **Message Sampling**: Automatically samples messages if they exceed token limits
- **IRC-Safe Output**: Splits long responses using the `!more` command
- **Configurable**: Default time window, maximum hours, and message limits
- **Per-Channel Control**: Enable/disable the plugin per channel

## Installation

1. Place the `recap` directory in your Limnoria plugins directory
2. Install the Anthropic SDK:
   ```bash
   pip install anthropic
   ```
3. Load the plugin in your bot:
   ```
   /msg botname load Recap
   ```

## Configuration

### Required: Set Your Anthropic API Key

```
/msg botname config supybot.plugins.anthropic.apiKey <your-api-key>
```

### Optional Configuration

- `supybot.plugins.Recap.defaultHours` (default: 5) - Default recap duration in hours
- `supybot.plugins.Recap.maxHours` (default: 24) - Maximum recap duration allowed
- `supybot.plugins.Recap.maxMessages` (default: 500) - Maximum messages to include (to limit token usage)
- `supybot.plugins.Recap.enabled` - Enable/disable per channel (default: True)

## Usage

### Get a recap of the last 5 hours (default):
```
!recap
```

### Get a recap of a specific time period:
```
!recap 3
```

### View more of the summary if it was truncated:
```
!more
```

## Examples

**User**: `!recap`
**Bot**: Generating summary...
**Bot**: The channel discussed database optimization strategies. Key topic was indexing performance, with consensus to benchmark before implementing changes.

**User**: `!recap 12`
**Bot**: Generating summary...
**Bot**: Channel covered feature roadmap planning and had extensive discussion on new authentication system implementation...
**Bot**: (to view more) `!more`

## Token Optimization

This plugin minimizes token usage through:

- **Model Selection**: Uses Claude 3.5 Haiku, the most cost-effective model
- **Message Sampling**: If message count exceeds `maxMessages`, the plugin intelligently samples messages
- **Compact Formatting**: Minimal prompt engineering with focused summaries (2-3 sentences max)
- **Short Response Limit**: Configured to return 150 tokens max per summary

## How It Works

1. Plugin automatically captures all channel messages
2. When `!recap` is called, it retrieves messages from the specified time window
3. Messages are formatted and sent to Claude Haiku for summarization
4. Response is split into IRC-safe chunks (max 420 chars per line)
5. User can use `!more` to see additional chunks

## License

BSD License (see plugin headers)
