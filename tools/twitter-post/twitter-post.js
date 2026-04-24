#!/usr/bin/env node
/**
 * Twitter Post — Fallback chain: bird CLI → Twitter API (x-post)
 * If all fail, outputs the tweet text for manual posting.
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const args = process.argv.slice(2);

if (args.length === 0 || args[0] === '--help') {
  console.log('Usage: node twitter-post.js <tweet|text> [--reply tweet-id]');
  console.log('       node twitter-post.js "Hello world"');
  console.log('       node twitter-post.js "Replying to you" --reply 123456789');
  console.log('');
  console.log('Fallback chain: bird CLI → Twitter API (x-post/post.js)');
  process.exit(0);
}

const text = args[0];
const replyIndex = args.indexOf('--reply');
const replyTo = replyIndex !== -1 ? args[replyIndex + 1] : null;

// Path to the Twitter API fallback
const xPostPath = path.join(process.env.HOME, 'clawd', 'tools', 'x-post', 'post.js');

function tryBird() {
  console.log('📤 Attempting bird CLI...');
  try {
    const escapedText = text.replace(/"/g, '\\"');
    const cmd = replyTo
      ? `bird reply ${replyTo} "${escapedText}"`
      : `bird tweet "${escapedText}"`;

    const output = execSync(cmd, {
      encoding: 'utf8',
      stdio: 'pipe',
      timeout: 30000
    });

    console.log('✅ Posted via bird CLI');
    if (output.trim()) console.log(output.trim());
    return true;
  } catch (error) {
    const msg = error.stderr || error.stdout || error.message || '';
    if (msg.includes('226') || msg.includes('344') || msg.includes('automated')) {
      console.log('❌ bird CLI blocked (Error 226/344 — anti-automation)');
    } else {
      console.log('❌ bird CLI failed:', msg.slice(0, 200));
    }
    return false;
  }
}

function tryTwitterApi() {
  console.log();
  console.log('📤 Attempting Twitter API (x-post)...');
  try {
    const escapedText = text.replace(/"/g, '\\"');
    const cmd = `node "${xPostPath}" "${escapedText}"${replyTo ? ` --reply ${replyTo}` : ''}`;
    const output = execSync(cmd, {
      encoding: 'utf8',
      stdio: 'pipe',
      timeout: 30000
    });
    console.log('✅ Posted via Twitter API');
    if (output.trim()) console.log(output.trim());
    return true;
  } catch (error) {
    const msg = error.stderr || error.stdout || error.message || '';
    console.log('❌ Twitter API failed:', msg.slice(0, 200));
    return false;
  }
}

function main() {
  console.log('🚀 Twitter Post — Fallback Chain');
  console.log('─'.repeat(40));
  console.log(`Text: "${text.slice(0, 100)}${text.length > 100 ? '...' : ''}"`);
  if (replyTo) console.log(`Reply to: ${replyTo}`);
  console.log('─'.repeat(40));
  console.log();

  // Step 1: Try bird CLI
  if (tryBird()) {
    process.exit(0);
  }

  // Step 2: Try Twitter API
  if (tryTwitterApi()) {
    process.exit(0);
  }

  // Step 3: All automated methods failed
  console.log();
  console.log('⚠️  All automated methods failed.');
  console.log('📋 Manual posting required:');
  console.log(`   ${text}`);
  if (replyTo) console.log(`   (Reply to: https://x.com/i/status/${replyTo})`);
  console.log();
  console.log('🔗 https://x.com');
  process.exit(1);
}

main();
