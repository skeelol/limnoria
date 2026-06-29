###
# Copyright (c) 2026, skeelol
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

from supybot.commands import *
from supybot import callbacks

import time
from collections import deque
from datetime import datetime

try:
    import anthropic
except ImportError:
    raise callbacks.Error('This plugin requires the anthropic package. '
                         'Install it with: pip install anthropic==0.7.1')

from . import config

class Recap(callbacks.Plugin):
    """Summarizes channel chat activity using Claude Haiku for token efficiency."""

    def __init__(self, irc):
        super().__init__(irc)
        # Store chat history per channel: {channel: deque of (timestamp, nick, message)}
        self.chat_history = {}
        # Store pending summaries: {channel: summary_data}
        self.pending_summaries = {}

    def _get_api_key(self):
        """Retrieve the Anthropic API key from config."""
        api_key = config.conf.supybot.plugins.anthropic.apiKey()
        if not api_key:
            raise callbacks.Error('Anthropic API key not configured. '
                                'Set supybot.plugins.anthropic.apiKey')
        return api_key

    def _initialize_channel(self, channel):
        """Initialize chat history for a channel."""
        if channel not in self.chat_history:
            self.chat_history[channel] = deque(maxlen=2000)  # Keep last 2000 messages

    def doPrivmsg(self, irc, msg):
        """Capture all channel messages for recap history."""
        if not msg.args:
            return
        
        channel = msg.args[0]
        
        # Only capture from channels (not private messages)
        if not irc.isChannel(channel):
            return
        
        # Check if plugin is enabled for this channel
        if not config.Recap.enabled.get(channel):
            return
        
        self._initialize_channel(channel)
        
        # Skip bot messages and commands
        if msg.nick == irc.nick:
            return
        
        text = msg.args[1]
        
        # Store message with timestamp
        self.chat_history[channel].append((
            time.time(),
            msg.nick,
            text
        ))

    def _get_recent_messages(self, channel, hours):
        """Get messages from the past N hours, with token optimization."""
        if channel not in self.chat_history:
            return []
        
        cutoff_time = time.time() - (hours * 3600)
        max_messages = config.Recap.maxMessages()
        
        # Collect messages within time window
        messages = []
        for timestamp, nick, text in self.chat_history[channel]:
            if timestamp >= cutoff_time:
                messages.append((timestamp, nick, text))
        
        # If we have too many messages, sample them to stay under token limit
        if len(messages) > max_messages:
            # Keep first and last messages, sample middle ones
            step = len(messages) // max_messages
            sampled = messages[::step][:max_messages]
            messages = sampled
        
        return messages

    def _format_messages_for_ai(self, messages):
        """Format messages for Claude Haiku with minimal tokens."""
        if not messages:
            return "No messages found in this time period."
        
        formatted = []
        for timestamp, nick, text in messages:
            # Compact format to minimize tokens
            dt = datetime.fromtimestamp(timestamp).strftime('%H:%M')
            formatted.append(f"{dt} {nick}: {text}")
        
        return "\n".join(formatted)

    def _summarize_with_claude(self, messages_text, hours):
        """Call Claude Haiku API to summarize messages efficiently."""
        api_key = self._get_api_key()
        client = anthropic.Anthropic(api_key=api_key)
        
        prompt = f"""Summarize the following {hours}-hour chat history concisely in 2-3 sentences maximum. 
Focus on main topics discussed and any important decisions or announcements.

Chat history:
{messages_text}

Provide a brief, factual summary:"""
        
        try:
            message = client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=150,  # Keep response short to minimize tokens
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except anthropic.APIError as e:
            raise callbacks.Error(f'Claude API error: {str(e)}')

    def _split_message(self, text, max_length=420):
        """Split text into IRC-safe chunks using the !more command."""
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_length = 0
        
        for line in lines:
            line_length = len(line) + 1  # +1 for newline
            if current_length + line_length > max_length and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks

    def recap(self, irc, msg, args, hours):
        """[<hours>]
        
        Summarizes the past <hours> of channel activity. If <hours> is not specified,
        defaults to 5 hours. Maximum is 24 hours.
        
        Example: !recap or !recap 3
        """
        channel = msg.args[0]
        
        # Check if plugin is enabled for this channel
        if not config.Recap.enabled.get(channel):
            irc.reply("Recap plugin is not enabled for this channel.")
            return
        
        # Set default hours if not provided
        if not hours:
            hours = config.Recap.defaultHours()
        
        # Validate hours
        max_hours = config.Recap.maxHours()
        if hours > max_hours:
            irc.reply(f"Maximum recap duration is {max_hours} hours. Using {max_hours} hours instead.")
            hours = max_hours
        
        # Ensure we have chat history initialized
        self._initialize_channel(channel)
        
        # Get recent messages
        messages = self._get_recent_messages(channel, hours)
        
        if not messages:
            irc.reply(f"No messages found in the past {hours} hour(s).")
            return
        
        # Format messages for AI
        messages_text = self._format_messages_for_ai(messages)
        
        # Generate summary
        try:
            irc.reply("Generating summary...")
            summary = self._summarize_with_claude(messages_text, hours)
        except callbacks.Error as e:
            irc.reply(str(e))
            return
        
        # Split response into IRC-safe chunks
        chunks = self._split_message(summary)
        
        # Send first chunk
        if chunks:
            irc.reply(chunks[0])
            # Store remaining chunks for !more command
            if len(chunks) > 1:
                self.pending_summaries[channel] = chunks[1:]
    
    recap = wrap(recap, [optional('int')])

    def more(self, irc, msg, args):
        """Takes no arguments.
        
        Displays the next part of the most recent recap summary.
        """
        channel = msg.args[0]
        
        if channel not in self.pending_summaries or not self.pending_summaries[channel]:
            irc.reply("No more recap data to display. Use !recap to generate a new summary.")
            return
        
        # Get next chunk
        next_chunk = self.pending_summaries[channel].pop(0)
        irc.reply(next_chunk)
        
        # Clean up if no more chunks
        if not self.pending_summaries[channel]:
            del self.pending_summaries[channel]
    
    more = wrap(more)

Class = Recap
