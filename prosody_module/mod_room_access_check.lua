-- mod_room_access_check.lua
-- Custom Prosody module to validate room access via external HTTP API
-- 
-- Installation:
-- 1. Copy this file to /usr/share/jitsi-meet/prosody-plugins/
-- 2. Add to your prosody config: modules_enabled = { "room_access_check" }
-- 3. Configure the check URL in prosody config
--
-- Configuration in /etc/prosody/conf.d/jitsi.cfg.lua:
--   room_access_check_url = "http://YOUR_DASHBOARD_IP:8000/api/check-room/"

local http = require "net.http";
local json = require "util.json";
local async = require "util.async";

local check_url = module:get_option_string("room_access_check_url", "http://localhost:8000/api/check-room/");
local check_timeout = module:get_option_number("room_access_check_timeout", 5);

module:log("info", "Room access check module loaded, URL: %s", check_url);

-- Cache for room access results (to reduce API calls)
local access_cache = {};
local cache_ttl = 60; -- Cache results for 60 seconds

local function check_room_access(room_name)
    local now = os.time();
    
    -- Check cache first
    if access_cache[room_name] and access_cache[room_name].expires > now then
        module:log("debug", "Cache hit for room: %s, allowed: %s", room_name, tostring(access_cache[room_name].allowed));
        return access_cache[room_name].allowed;
    end
    
    -- Make HTTP request to check room access
    local url = check_url .. "?room_name=" .. http.urlencode(room_name);
    
    local wait, done = async.waiter();
    local result = nil;
    
    http.request(url, {
        method = "GET";
        headers = {
            ["Accept"] = "application/json";
        };
    }, function(response_body, response_code)
        if response_code == 200 then
            local ok, data = pcall(json.decode, response_body);
            if ok and data then
                result = data.allowed;
                -- Cache the result
                access_cache[room_name] = {
                    allowed = result,
                    expires = now + cache_ttl
                };
                module:log("info", "Room access check for '%s': allowed=%s", room_name, tostring(result));
            else
                module:log("warn", "Failed to parse response for room: %s", room_name);
                result = true; -- Allow on parse error (fail open)
            end
        else
            module:log("warn", "HTTP error %s checking room: %s", tostring(response_code), room_name);
            result = true; -- Allow on HTTP error (fail open)
        end
        done();
    end);
    
    -- Wait for response with timeout
    local success = wait(check_timeout);
    if not success then
        module:log("warn", "Timeout checking room access for: %s", room_name);
        return true; -- Allow on timeout (fail open)
    end
    
    return result ~= false; -- Default to allowed if result is nil
end

-- Hook into MUC room join
module:hook("muc-occupant-pre-join", function(event)
    local room = event.room;
    local stanza = event.stanza;
    local occupant = event.occupant;
    
    -- Extract room name from JID
    local room_jid = room.jid;
    local room_name = room_jid:match("^([^@]+)");
    
    if not room_name then
        module:log("warn", "Could not extract room name from JID: %s", room_jid);
        return;
    end
    
    -- Skip check for certain system rooms (lobby, etc)
    if room_name:find("^lobby%.") then
        module:log("debug", "Skipping access check for lobby room: %s", room_name);
        return;
    end
    
    module:log("debug", "Checking access for room: %s", room_name);
    
    local allowed = check_room_access(room_name);
    
    if not allowed then
        module:log("info", "Blocking access to revoked room: %s for %s", room_name, occupant.bare_jid);
        
        -- Send error response
        local error_reply = st.error_reply(stanza, "cancel", "not-allowed", "This meeting has been deleted.");
        event.origin.send(error_reply);
        
        return true; -- Stop further processing
    end
end, 10); -- Priority 10 (higher = runs earlier)

-- Clean up expired cache entries periodically
module:add_timer(300, function()
    local now = os.time();
    local cleaned = 0;
    for room_name, entry in pairs(access_cache) do
        if entry.expires < now then
            access_cache[room_name] = nil;
            cleaned = cleaned + 1;
        end
    end
    if cleaned > 0 then
        module:log("debug", "Cleaned %d expired cache entries", cleaned);
    end
    return 300; -- Run again in 5 minutes
end);

module:log("info", "Room access check module initialized");
