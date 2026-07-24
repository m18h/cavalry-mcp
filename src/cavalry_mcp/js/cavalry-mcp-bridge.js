// cavalry-mcp bridge VERSION 0.1.0
//
// cavalry-mcp bridge — an HTTP request/response bridge for the cavalry-mcp
// server (https://github.com/). Runs inside Cavalry as a UI script.
//
// Protocol
// --------
//   Client  POST http://127.0.0.1:8722/post   body: {"id": "<uuid>", "code": "<js>"}
//   Bridge  executes `code` via eval (wrapped in an IIFE — use `return` to send
//           a value back), captures the return value, console output and errors.
//   Client  polls GET http://127.0.0.1:8722/get until the JSON payload's `id`
//           matches its request:
//           {"type": "result", "id": "<uuid>", "ok": true,
//            "value": <json>, "logs": [...], "error": null}
//
// Install: copy this file into the Cavalry Scripts folder
//   macOS:   ~/Library/Application Support/Cavalry/Scripts/
//   Windows: %APPDATA%/Cavalry/Scripts/
// then start it from Cavalry's Scripts menu. Keep the window open while using
// cavalry-mcp.

var BRIDGE_VERSION = '0.1.0'
var MIN_CAVALRY_VERSION = '2.4.0'
var HOST = '127.0.0.1'
var PORT = 8722

if (cavalry.versionLessThan(MIN_CAVALRY_VERSION)) {
	throw new Error(
		'cavalry-mcp bridge requires Cavalry ' +
			MIN_CAVALRY_VERSION +
			' or higher',
	)
}

var server = new api.WebServer()

// File-based debugging: flip to true to trace bridge activity to DEBUG_LOG.
var DEBUG = false
var DEBUG_LOG = '/tmp/cavalry-mcp-bridge-debug.log'

function debug(message) {
	if (!DEBUG) {
		return
	}
	try {
		var existing = api.filePathExists(DEBUG_LOG)
			? api.readFromFile(DEBUG_LOG)
			: ''
		api.writeToFile(
			DEBUG_LOG,
			existing + '\n' + new Date().toISOString() + ' ' + message,
		)
	} catch (err) {
		// Debugging must never break the bridge.
	}
}

// ---------------------------------------------------------------------------
// Execution helpers
// ---------------------------------------------------------------------------

function jsonSafe(value) {
	// JSON.stringify can fail on circular structures or Cavalry host objects.
	if (value === undefined) {
		return null
	}
	try {
		var text = JSON.stringify(value)
		if (text === undefined) {
			return null
		}
		return JSON.parse(text)
	} catch (err) {
		try {
			return String(value)
		} catch (err2) {
			return '[unserializable value]'
		}
	}
}

function execute(code) {
	var logs = []
	var original = {}
	var levels = ['log', 'info', 'warn', 'error']
	levels.forEach(function (level) {
		original[level] = console[level]
		console[level] = function () {
			var parts = []
			for (var i = 0; i < arguments.length; i++) {
				var arg = arguments[i]
				var text
				try {
					text =
						typeof arg === 'string' ? arg : JSON.stringify(arg)
				} catch (err) {
					text = String(arg)
				}
				parts.push(text)
			}
			logs.push({ level: level, message: parts.join(' ') })
			original[level].apply(console, arguments)
		}
	})

	var response = { type: 'result', id: null, ok: true, value: null, logs: logs, error: null }
	try {
		// Wrapped in an IIFE so `var`/`function` declarations in the snippet do
		// not leak into (and potentially break) the bridge's own scope.
		response.value = jsonSafe(eval('(function() {\n' + code + '\n})()'))
	} catch (err) {
		response.ok = false
		response.error = {
			message: String(err && err.message ? err.message : err),
			stack: String(err && err.stack ? err.stack : ''),
		}
	} finally {
		levels.forEach(function (level) {
			console[level] = original[level]
		})
	}
	return response
}

// ---------------------------------------------------------------------------
// Server callbacks
// ---------------------------------------------------------------------------

// NOTE: onPost must be an OWN property of the callback object (matching the
// official docs example and Stallion's compiled output) — Cavalry's native
// side may not resolve prototype methods.
function BridgeCallbacks() {
	this.onPost = function () {
		debug('onPost fired, queued: ' + server.postCount())
		while (server.postCount() > 0) {
			var post = server.getNextPost()
			var request
			try {
				request = JSON.parse(post.result)
			} catch (err) {
				console.error('cavalry-mcp bridge: request was not valid JSON')
				continue
			}
			if (!request.id || !request.code) {
				console.error('cavalry-mcp bridge: request needs `id` and `code` keys')
				continue
			}
			debug('executing ' + request.id)
			var response = execute(String(request.code))
			response.id = String(request.id)
			server.setResultForGet(JSON.stringify(response))
			debug('result published for ' + request.id)
		}
	}
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

// Initial payload lets clients probe readiness before sending any work.
server.setResultForGet(
	JSON.stringify({
		type: 'hello',
		bridge: 'cavalry-mcp',
		bridgeVersion: BRIDGE_VERSION,
		cavalryVersion: api.getCavalryVersion(),
	}),
)

server.listen(HOST, PORT)
debug('listening on ' + HOST + ':' + PORT)
var callbacks = new BridgeCallbacks()
server.addCallbackObject(callbacks)
// NOTE: setRealtime() (60/sec) appears to break post polling on Cavalry 2.7.2;
// setHighFrequency() (1/sec) is what Stallion uses and is proven to work.
// Results therefore arrive within ~1 second of a request.
server.setHighFrequency()

var Align = { CENTRE: 1 }
var title = new ui.Label('cavalry-mcp bridge v' + BRIDGE_VERSION)
title.setAlignment(Align.CENTRE)
var status = new ui.Label('Listening on http://' + HOST + ':' + PORT)
status.setAlignment(Align.CENTRE)
var hint = new ui.Label('Keep this window open while using cavalry-mcp.')
hint.setAlignment(Align.CENTRE)

var layout = new ui.VLayout()
layout.addStretch()
layout.add(title, status, hint)
layout.addStretch()
ui.setTitle('cavalry-mcp bridge')
ui.add(layout)
ui.show()

console.log('cavalry-mcp bridge v' + BRIDGE_VERSION + ' listening on ' + HOST + ':' + PORT)
