#include <ultra64.h>
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "constants.h"
#include "types.h"
#include "bss.h"
#include "data.h"
#include "system.h"
#include "config.h"
#include "bootmp.h"
#include "office_service_bridge.h"
#include "input.h"
#include "game/menu.h"
#include "game/hudmsg.h"

#if !defined(PLATFORM_N64) && PLATFORM_POSIX

#include <arpa/inet.h>
#include <netinet/in.h>
#include <pthread.h>
#include <sys/socket.h>
#include <unistd.h>

#define OFFICE_SUMMARY_CAP 384
#define OFFICE_HTTP_BODY_CAP 32768
#define OFFICE_PERFECT_MENU_CAP 1536
#define OFFICE_MONITOR_TEXT_CAP 384
#define OFFICE_MONITOR_AGENT_ID_CAP 32
#define OFFICE_MONITOR_AGENT_MAX 8
#define OFFICE_DM_HUD_CAP 384
#define OFFICE_VISOR_NOTIFY_CAP 256
#define OFFICE_VISOR_RAIL_CAP 768
#define OFFICE_VISOR_SCROLLBACK_CAP 1024
#define OFFICE_VISOR_COMPOSE_AGENT_CAP 32
#define OFFICE_VISOR_COMPOSE_TEXT_CAP 128
#define OFFICE_VISOR_COMPOSE_HINT_CAP 128
#define OFFICE_VISOR_COMPOSE_PICKER_CAP 128
#define OFFICE_VISOR_COMPOSE_PICKER_MAX 4
#define OFFICE_VK_TAB 43 /* SDL_SCANCODE_TAB — cycle visor compose agent picker (Pass 23). */
#define OFFICE_VISOR_COMPOSE_FEEDBACK_CAP 256
#define OFFICE_VISOR_COMPOSE_COOLDOWN_US (10 * 1000 * 1000)
#define OFFICE_VISOR_COMPOSE_INPUT_USER_CAP 120
#define OFFICE_VISOR_COMPOSE_INPUT_HUD_CAP 192
#define OFFICE_VISOR_COMPOSE_PREFIX "visor: "
#define OFFICE_SECURITY_CONNECTOR_ID_CAP 64
#define OFFICE_SECURITY_CONNECTOR_HUD_CAP 384
#define OFFICE_SECURITY_CONNECTOR_FEEDBACK_CAP 256
#define OFFICE_SECURITY_CONNECTOR_PICKER_MAX 4
#define OFFICE_SECURITY_CONNECTOR_PICKER_CAP 256
#define OFFICE_SECURITY_CONNECTOR_PICKER_HUDS_CAP 1600
#define OFFICE_COMMS_CONNECTOR_HUD_CAP 384
#define OFFICE_COMMS_CONNECTOR_INTENT_CAP 128
#define OFFICE_COMMS_CONNECTOR_CHANNEL_CAP 64
#define OFFICE_COMMS_CONNECTOR_TEXT_CAP 256
#define OFFICE_COMMS_CONNECTOR_FEEDBACK_CAP 256
#define OFFICE_COMMS_CONNECTOR_STAGE_COOLDOWN_US (10 * 1000 * 1000)
#define OFFICE_POLL_INTERVAL_US (4 * 1000 * 1000)
#define OFFICE_HTTP_TIMEOUT_MS 400
#define OFFICE_DM_COOLDOWN_US (3 * 1000 * 1000)
#define OFFICE_POLL_THREAD_SLEEP_US (250 * 1000)

static s32 g_OfficeServiceEnabled = 1;
static s32 g_OfficeServicePort = OFFICE_SERVICE_DEFAULT_PORT;
/* Evidence / automation: BOOT_OPEN_CONSOLE=1 or --boot-open-console opens Perfect Menu once. */
static s32 g_OfficeBootOpenConsole = 0;
static s32 g_OfficeBootOpenDone = 0;
static s32 g_OfficeBootOpenWaitTicks = 0;
static char g_OfficeLiveSummary[OFFICE_SUMMARY_CAP];
static s32 g_OfficeLiveSummaryLen = 0;
/* R3: Perfect Menu overview + per-desk monitor_text from GET /fleet. */
static char g_OfficePerfectMenuText[OFFICE_PERFECT_MENU_CAP];
static s32 g_OfficePerfectMenuTextLen = 0;
static char g_OfficeMonitorAgentIds[OFFICE_MONITOR_AGENT_MAX][OFFICE_MONITOR_AGENT_ID_CAP];
static char g_OfficeMonitorTexts[OFFICE_MONITOR_AGENT_MAX][OFFICE_MONITOR_TEXT_CAP];
static s32 g_OfficeMonitorCount = 0;
static char g_OfficeDmHudText[OFFICE_DM_HUD_CAP];
static s32 g_OfficeDmHudTextLen = 0;
static char g_OfficeVisorNotification[OFFICE_VISOR_NOTIFY_CAP];
static s32 g_OfficeVisorNotificationLen = 0;
static char g_OfficeVisorRail[OFFICE_VISOR_RAIL_CAP];
static s32 g_OfficeVisorRailLen = 0;
static char g_OfficeVisorScrollback[OFFICE_VISOR_SCROLLBACK_CAP];
static s32 g_OfficeVisorScrollbackLen = 0;
static char g_OfficeVisorComposeAgentId[OFFICE_VISOR_COMPOSE_AGENT_CAP];
static s32 g_OfficeVisorComposeAgentIdLen = 0;
static char g_OfficeVisorComposeText[OFFICE_VISOR_COMPOSE_TEXT_CAP];
static s32 g_OfficeVisorComposeTextLen = 0;
static char g_OfficeVisorComposeHint[OFFICE_VISOR_COMPOSE_HINT_CAP];
static s32 g_OfficeVisorComposeHintLen = 0;
static char g_OfficeVisorComposePicker[OFFICE_VISOR_COMPOSE_PICKER_CAP];
static s32 g_OfficeVisorComposePickerLen = 0;
static u64 g_OfficeLastFetchUs = 0;
static u64 g_OfficeLastAttemptUs = 0;
static u64 g_OfficeLastDmAttemptUs = 0;
static u32 g_OfficeLastDmTextId = 0;

/* Pass 11: background poll thread — GET /slack/channels + GET /dm off main thread. */
static pthread_mutex_t g_OfficePollCacheMutex = PTHREAD_MUTEX_INITIALIZER;
static pthread_t g_OfficePollThread;
static volatile s32 g_OfficePollStop = 0;
static volatile s32 g_OfficePollThreadRunning = 0;

/* Pass 13: async walk-up POST queue — main enqueues, worker executes HTTP. */
static pthread_mutex_t g_OfficeWalkUpMutex = PTHREAD_MUTEX_INITIALIZER;
static u32 g_OfficeWalkUpPendingTextId = 0;
static char g_OfficeWalkUpPendingAgentId[32];
static volatile s32 g_OfficeWalkUpPending = 0;

/* Pass 15: HUD auto-refresh while Z-targeting after async walk-up completes. */
static s16 g_OfficeDmWaitChrnum = -1;
static u32 g_OfficeDmWaitTextId = 0;
static volatile s32 g_OfficeDmRefreshReady = 0;

/* Pass 21: async visor pause compose POST /dm/{agent_id} — main enqueues, worker executes. */
static pthread_mutex_t g_OfficeVisorComposeMutex = PTHREAD_MUTEX_INITIALIZER;
static volatile s32 g_OfficeVisorComposePending = 0;
static char g_OfficeVisorComposePendingAgentId[OFFICE_VISOR_COMPOSE_AGENT_CAP];
static char g_OfficeVisorComposePendingText[OFFICE_VISOR_COMPOSE_TEXT_CAP];
static char g_OfficeVisorComposeFeedback[OFFICE_VISOR_COMPOSE_FEEDBACK_CAP];
static volatile s32 g_OfficeVisorComposeFeedbackReady = 0;
static u64 g_OfficeLastVisorComposeUs = 0;

/* Pass 22: visor pause keyboard compose — SDL text input while pause menu is open. */
static volatile s32 g_OfficeVisorComposeInputActive = 0;
static char g_OfficeVisorComposeInputUser[OFFICE_VISOR_COMPOSE_INPUT_USER_CAP];
static s32 g_OfficeVisorComposeInputCursor = 0;
static char g_OfficeVisorComposeInputAgentId[OFFICE_VISOR_COMPOSE_AGENT_CAP];
static char g_OfficeVisorComposeInputHud[OFFICE_VISOR_COMPOSE_INPUT_HUD_CAP];
static char g_OfficeVisorComposeInputLastHud[OFFICE_VISOR_COMPOSE_INPUT_HUD_CAP];
static char g_OfficeVisorComposePickerAgents[OFFICE_VISOR_COMPOSE_PICKER_MAX][OFFICE_VISOR_COMPOSE_AGENT_CAP];
static s32 g_OfficeVisorComposePickerCount = 0;
static s32 g_OfficeVisorComposePickerIndex = 0;

/* Pass 35: Security desk Z-target connector approval — poll cache + async POST queue. */
static char g_OfficeSecurityConnectorApprovalId[OFFICE_SECURITY_CONNECTOR_ID_CAP];
static s32 g_OfficeSecurityConnectorApprovalIdLen = 0;
static char g_OfficeSecurityConnectorHud[OFFICE_SECURITY_CONNECTOR_HUD_CAP];
static s32 g_OfficeSecurityConnectorHudLen = 0;
static pthread_mutex_t g_OfficeSecurityConnectorMutex = PTHREAD_MUTEX_INITIALIZER;
static volatile s32 g_OfficeSecurityConnectorActionPending = 0;
static char g_OfficeSecurityConnectorPendingApprovalId[OFFICE_SECURITY_CONNECTOR_ID_CAP];
static volatile s32 g_OfficeSecurityConnectorPendingApprove = 0;
static char g_OfficeSecurityConnectorFeedback[OFFICE_SECURITY_CONNECTOR_FEEDBACK_CAP];
static volatile s32 g_OfficeSecurityConnectorFeedbackReady = 0;
static s16 g_OfficeSecurityConnectorWaitChrnum = -1;
static u32 g_OfficeSecurityConnectorWaitTextId = 0;
static volatile s32 g_OfficeSecurityConnectorBusy = 0;
static char g_OfficeSecurityConnectorPickerIds[OFFICE_SECURITY_CONNECTOR_PICKER_MAX][OFFICE_SECURITY_CONNECTOR_ID_CAP];
static char g_OfficeSecurityConnectorPickerHuds[OFFICE_SECURITY_CONNECTOR_PICKER_MAX][OFFICE_SECURITY_CONNECTOR_HUD_CAP];
static s32 g_OfficeSecurityConnectorPickerCount = 0;
static s32 g_OfficeSecurityConnectorPickerIndex = 0;

/* Pass 37: Comms desk Z-target connector stage — poll cache + async dispatch/perform queue. */
static char g_OfficeCommsConnectorStageHud[OFFICE_COMMS_CONNECTOR_HUD_CAP];
static s32 g_OfficeCommsConnectorStageHudLen = 0;
static char g_OfficeCommsConnectorStageIntent[OFFICE_COMMS_CONNECTOR_INTENT_CAP];
static s32 g_OfficeCommsConnectorStageIntentLen = 0;
static char g_OfficeCommsConnectorStageChannel[OFFICE_COMMS_CONNECTOR_CHANNEL_CAP];
static s32 g_OfficeCommsConnectorStageChannelLen = 0;
static char g_OfficeCommsConnectorStageText[OFFICE_COMMS_CONNECTOR_TEXT_CAP];
static s32 g_OfficeCommsConnectorStageTextLen = 0;
static pthread_mutex_t g_OfficeCommsConnectorMutex = PTHREAD_MUTEX_INITIALIZER;
static volatile s32 g_OfficeCommsConnectorStagePending = 0;
static char g_OfficeCommsConnectorPendingIntent[OFFICE_COMMS_CONNECTOR_INTENT_CAP];
static char g_OfficeCommsConnectorPendingChannel[OFFICE_COMMS_CONNECTOR_CHANNEL_CAP];
static char g_OfficeCommsConnectorPendingText[OFFICE_COMMS_CONNECTOR_TEXT_CAP];
static char g_OfficeCommsConnectorFeedback[OFFICE_COMMS_CONNECTOR_FEEDBACK_CAP];
static volatile s32 g_OfficeCommsConnectorFeedbackReady = 0;
static s16 g_OfficeCommsConnectorWaitChrnum = -1;
static u32 g_OfficeCommsConnectorWaitTextId = 0;
static volatile s32 g_OfficeCommsConnectorBusy = 0;
static u64 g_OfficeLastCommsConnectorStageUs = 0;

static void *officePollThreadMain(void *arg);
static void officeWalkUpProcessPending(void);
static void officeWalkUpEnqueue(u32 text_id, const char *agent_id);
static void officeVisorComposeProcessPending(void);
static void officeVisorComposeEnqueue(const char *agent_id, const char *text);
static void officeVisorComposeDoSubmit(const char *agent_id, const char *text);
static void officeVisorComposeParsePicker(void);
static void officeSecurityConnectorProcessPending(void);
static void officeSecurityConnectorEnqueue(const char *approval_id, s32 approve);
static s32 officeSecurityConnectorIsSecurityText(u32 text_id);
static void officeSecurityConnectorParsePicker(const char *picker_ids, const char *picker_huds);
static void officeSecurityConnectorSyncSelected(void);
static void officeCommsConnectorProcessPending(void);
static void officeCommsConnectorEnqueue(const char *intent, const char *channel, const char *text);
static s32 officeCommsConnectorIsCommsText(u32 text_id);

static u64 officeNowUs(void)
{
	return sysGetMicroseconds();
}

static s32 officeHubActive(void)
{
	return agentOfficeHubAnyActive() ? 1 : 0;
}

static s32 officeConsoleTextMatchesStage(u32 text_id)
{
	if (text_id == OFFICE_CONSOLE_TEXT_CI && agentOfficeHubUsesCiPads()) {
		return 1;
	}
	if (text_id == OFFICE_CONSOLE_TEXT_G5 && agentOfficeHubUsesG5Pads()) {
		return 1;
	}
	return 0;
}

static s32 officeSetSocketTimeoutMs(int fd, s32 ms)
{
	struct timeval tv;

	tv.tv_sec = ms / 1000;
	tv.tv_usec = (ms % 1000) * 1000;
	if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) != 0) {
		return 0;
	}
	if (setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv)) != 0) {
		return 0;
	}
	return 1;
}

static s32 officeExtractJsonString(const char *json, const char *key, char *out, s32 outCap)
{
	char pattern[64];
	const char *pos;
	const char *start;
	const char *p;
	s32 len;

	if (!json || !key || !out || outCap < 2) {
		return 0;
	}

	snprintf(pattern, sizeof(pattern), "\"%s\"", key);
	pos = strstr(json, pattern);
	if (!pos) {
		return 0;
	}

	pos = strchr(pos, ':');
	if (!pos) {
		return 0;
	}
	pos++;
	while (*pos == ' ' || *pos == '\t' || *pos == '\n' || *pos == '\r') {
		pos++;
	}
	if (*pos != '"') {
		return 0;
	}
	start = pos + 1;
	p = start;
	while (*p && *p != '"') {
		if (*p == '\\' && p[1]) {
			p += 2;
		} else {
			p++;
		}
	}
	if (*p != '"') {
		return 0;
	}

	len = (s32)(p - start);
	if (len <= 0 || len >= outCap) {
		return 0;
	}

	memcpy(out, start, (size_t)len);
	out[len] = '\0';
	return 1;
}

static s32 officeHttpRequest(const char *method, const char *path, const char *jsonBody,
		char *bodyOut, s32 bodyCap)
{
	struct sockaddr_in addr;
	char req[OFFICE_HTTP_BODY_CAP];
	char resp[OFFICE_HTTP_BODY_CAP];
	int fd;
	s32 total;
	s32 sent;
	const char *body;
	s32 bodyLen;
	s32 contentLen = 0;

	if (!method || !path || !bodyOut || bodyCap < 16) {
		return 0;
	}

	if (jsonBody && jsonBody[0]) {
		contentLen = (s32)strlen(jsonBody);
	}

	fd = socket(AF_INET, SOCK_STREAM, 0);
	if (fd < 0) {
		return 0;
	}

	if (!officeSetSocketTimeoutMs(fd, OFFICE_HTTP_TIMEOUT_MS)) {
		close(fd);
		return 0;
	}

	memset(&addr, 0, sizeof(addr));
	addr.sin_family = AF_INET;
	addr.sin_port = htons((u16)g_OfficeServicePort);
	if (inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr) != 1) {
		close(fd);
		return 0;
	}

	if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
		close(fd);
		return 0;
	}

	if (contentLen > 0) {
		snprintf(req, sizeof(req),
				"%s %s HTTP/1.1\r\n"
				"Host: 127.0.0.1:%d\r\n"
				"Connection: close\r\n"
				"Accept: application/json\r\n"
				"Content-Type: application/json\r\n"
				"Content-Length: %d\r\n\r\n"
				"%s",
				method, path, g_OfficeServicePort, contentLen, jsonBody);
	} else {
		snprintf(req, sizeof(req),
				"%s %s HTTP/1.1\r\n"
				"Host: 127.0.0.1:%d\r\n"
				"Connection: close\r\n"
				"Accept: application/json\r\n\r\n",
				method, path, g_OfficeServicePort);
	}

	sent = 0;
	while (sent < (s32)strlen(req)) {
		s32 n = (s32)send(fd, req + sent, strlen(req) - (size_t)sent, 0);
		if (n <= 0) {
			close(fd);
			return 0;
		}
		sent += n;
	}

	total = 0;
	while (total < (s32)sizeof(resp) - 1) {
		s32 n = (s32)recv(fd, resp + total, sizeof(resp) - 1 - total, 0);
		if (n <= 0) {
			break;
		}
		total += n;
	}
	close(fd);

	if (total <= 0) {
		return 0;
	}
	resp[total] = '\0';

	body = strstr(resp, "\r\n\r\n");
	if (!body) {
		return 0;
	}
	body += 4;
	bodyLen = total - (s32)(body - resp);
	if (bodyLen <= 0 || bodyLen >= bodyCap) {
		return 0;
	}

	memcpy(bodyOut, body, (size_t)bodyLen);
	bodyOut[bodyLen] = '\0';
	return 1;
}

static s32 officeHttpGetSlackChannels(char *bodyOut, s32 bodyCap)
{
	return officeHttpRequest("GET", "/slack/channels", NULL, bodyOut, bodyCap);
}

static s32 officeHttpGetDmList(char *bodyOut, s32 bodyCap)
{
	return officeHttpRequest("GET", "/dm", NULL, bodyOut, bodyCap);
}

static s32 officeHttpGetFleet(char *bodyOut, s32 bodyCap)
{
	return officeHttpRequest("GET", "/fleet", NULL, bodyOut, bodyCap);
}

/* Parse embodied_agents[].agent_id + monitor_text pairs from GET /fleet JSON. */
static void officeParseFleetMonitors(const char *json)
{
	const char *p;
	s32 count = 0;

	g_OfficeMonitorCount = 0;
	if (!json || !json[0]) {
		return;
	}

	p = json;
	while (count < OFFICE_MONITOR_AGENT_MAX && (p = strstr(p, "\"agent_id\"")) != NULL) {
		char agentId[OFFICE_MONITOR_AGENT_ID_CAP];
		char monitor[OFFICE_MONITOR_TEXT_CAP];
		const char *sliceEnd;
		char slice[1024];
		s32 sliceLen;

		agentId[0] = '\0';
		monitor[0] = '\0';

		if (!officeExtractJsonString(p, "agent_id", agentId, sizeof(agentId))) {
			p += 10;
			continue;
		}

		sliceEnd = strstr(p + 10, "\"agent_id\"");
		sliceLen = sliceEnd ? (s32)(sliceEnd - p) : (s32)strlen(p);
		if (sliceLen <= 0) {
			break;
		}
		if (sliceLen >= (s32)sizeof(slice)) {
			sliceLen = (s32)sizeof(slice) - 1;
		}
		memcpy(slice, p, (size_t)sliceLen);
		slice[sliceLen] = '\0';

		if (!officeExtractJsonString(slice, "monitor_text", monitor, sizeof(monitor))) {
			/* monitor_text may contain escaped newlines; fall back to role/state. */
			char role[64];
			char state[64];

			role[0] = '\0';
			state[0] = '\0';
			officeExtractJsonString(slice, "role", role, sizeof(role));
			officeExtractJsonString(slice, "state", state, sizeof(state));
			if (role[0] && state[0]) {
				snprintf(monitor, sizeof(monitor), "%s: %s", role, state);
			}
		}

		/* Collapse escaped newlines from JSON strings into spaces for HUD/menu. */
		{
			char *q;

			for (q = monitor; *q; q++) {
				if (*q == '\\' && (q[1] == 'n' || q[1] == 'r' || q[1] == 't')) {
					*q = ' ';
					memmove(q + 1, q + 2, strlen(q + 1));
				} else if (*q == '\n' || *q == '\r' || *q == '\t') {
					*q = ' ';
				}
			}
		}

		if (agentId[0] && monitor[0]) {
			strncpy(g_OfficeMonitorAgentIds[count], agentId, sizeof(g_OfficeMonitorAgentIds[count]) - 1);
			g_OfficeMonitorAgentIds[count][sizeof(g_OfficeMonitorAgentIds[count]) - 1] = '\0';
			strncpy(g_OfficeMonitorTexts[count], monitor, sizeof(g_OfficeMonitorTexts[count]) - 1);
			g_OfficeMonitorTexts[count][sizeof(g_OfficeMonitorTexts[count]) - 1] = '\0';
			count++;
		}

		p += 10;
	}

	g_OfficeMonitorCount = count;
}

static void officePublishPollCache(const char *summary, const char *notify, const char *visorRail,
		const char *visorScrollback, u64 attemptUs)
{
	pthread_mutex_lock(&g_OfficePollCacheMutex);

	g_OfficeLastAttemptUs = attemptUs;
	g_OfficeLiveSummaryLen = 0;
	g_OfficeLiveSummary[0] = '\0';
	g_OfficeVisorNotificationLen = 0;
	g_OfficeVisorNotification[0] = '\0';
	g_OfficeVisorRailLen = 0;
	g_OfficeVisorRail[0] = '\0';
	g_OfficeVisorScrollbackLen = 0;
	g_OfficeVisorScrollback[0] = '\0';

	if (summary && summary[0]) {
		strncpy(g_OfficeLiveSummary, summary, sizeof(g_OfficeLiveSummary) - 1);
		g_OfficeLiveSummary[sizeof(g_OfficeLiveSummary) - 1] = '\0';
		g_OfficeLiveSummaryLen = (s32)strlen(g_OfficeLiveSummary);
		g_OfficeLastFetchUs = attemptUs;
	}

	if (notify && notify[0]) {
		strncpy(g_OfficeVisorNotification, notify, sizeof(g_OfficeVisorNotification) - 1);
		g_OfficeVisorNotification[sizeof(g_OfficeVisorNotification) - 1] = '\0';
		g_OfficeVisorNotificationLen = (s32)strlen(g_OfficeVisorNotification);
	}

	if (visorRail && visorRail[0]) {
		strncpy(g_OfficeVisorRail, visorRail, sizeof(g_OfficeVisorRail) - 1);
		g_OfficeVisorRail[sizeof(g_OfficeVisorRail) - 1] = '\0';
		g_OfficeVisorRailLen = (s32)strlen(g_OfficeVisorRail);
	}

	if (visorScrollback && visorScrollback[0]) {
		strncpy(g_OfficeVisorScrollback, visorScrollback, sizeof(g_OfficeVisorScrollback) - 1);
		g_OfficeVisorScrollback[sizeof(g_OfficeVisorScrollback) - 1] = '\0';
		g_OfficeVisorScrollbackLen = (s32)strlen(g_OfficeVisorScrollback);
	}

	pthread_mutex_unlock(&g_OfficePollCacheMutex);
}

/* Worker-only: HTTP for lobby summary + visor notification (never call from main thread). */
static void officeFetchPollCache(void)
{
	char body[OFFICE_HTTP_BODY_CAP];
	char summary[OFFICE_SUMMARY_CAP];
	char notify[OFFICE_VISOR_NOTIFY_CAP];
	char visorRail[OFFICE_VISOR_RAIL_CAP];
	char visorScrollback[OFFICE_VISOR_SCROLLBACK_CAP];
	char composeAgent[OFFICE_VISOR_COMPOSE_AGENT_CAP];
	char composeText[OFFICE_VISOR_COMPOSE_TEXT_CAP];
	char composeHint[OFFICE_VISOR_COMPOSE_HINT_CAP];
	char composePicker[OFFICE_VISOR_COMPOSE_PICKER_CAP];
	char securityConnectorId[OFFICE_SECURITY_CONNECTOR_ID_CAP];
	char securityConnectorHud[OFFICE_SECURITY_CONNECTOR_HUD_CAP];
	char securityConnectorPicker[OFFICE_SECURITY_CONNECTOR_PICKER_CAP];
	char securityConnectorPickerHuds[OFFICE_SECURITY_CONNECTOR_PICKER_HUDS_CAP];
	char commsConnectorStageHud[OFFICE_COMMS_CONNECTOR_HUD_CAP];
	char commsConnectorStageIntent[OFFICE_COMMS_CONNECTOR_INTENT_CAP];
	char commsConnectorStageChannel[OFFICE_COMMS_CONNECTOR_CHANNEL_CAP];
	char commsConnectorStageText[OFFICE_COMMS_CONNECTOR_TEXT_CAP];
	const u64 attemptUs = officeNowUs();

	if (!g_OfficeServiceEnabled) {
		officePublishPollCache(NULL, NULL, NULL, NULL, attemptUs);
		return;
	}

	summary[0] = '\0';
	notify[0] = '\0';
	visorRail[0] = '\0';
	visorScrollback[0] = '\0';
	composeAgent[0] = '\0';
	composeText[0] = '\0';
	composeHint[0] = '\0';
	composePicker[0] = '\0';
	securityConnectorId[0] = '\0';
	securityConnectorHud[0] = '\0';
	securityConnectorPicker[0] = '\0';
	securityConnectorPickerHuds[0] = '\0';
	commsConnectorStageHud[0] = '\0';
	commsConnectorStageIntent[0] = '\0';
	commsConnectorStageChannel[0] = '\0';
	commsConnectorStageText[0] = '\0';

	if (!officeHttpGetSlackChannels(body, sizeof(body))) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] GET /slack/channels failed (service down?)");
		officePublishPollCache(NULL, NULL, NULL, NULL, attemptUs);
		return;
	}

	if (!officeExtractJsonString(body, "general_summary", summary, sizeof(summary))) {
		summary[0] = '\0';
	}

	{
		char dmBody[OFFICE_HTTP_BODY_CAP];

		if (!officeHttpGetDmList(dmBody, sizeof(dmBody))) {
			notify[0] = '\0';
			visorRail[0] = '\0';
			visorScrollback[0] = '\0';
			composeAgent[0] = '\0';
			composeText[0] = '\0';
			composeHint[0] = '\0';
			composePicker[0] = '\0';
			securityConnectorId[0] = '\0';
			securityConnectorHud[0] = '\0';
			securityConnectorPicker[0] = '\0';
			securityConnectorPickerHuds[0] = '\0';
			commsConnectorStageHud[0] = '\0';
			commsConnectorStageIntent[0] = '\0';
			commsConnectorStageChannel[0] = '\0';
			commsConnectorStageText[0] = '\0';
		} else {
			if (!officeExtractJsonString(dmBody, "notification_stub", notify, sizeof(notify))) {
				notify[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "visor_rail", visorRail, sizeof(visorRail))) {
				visorRail[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "visor_scrollback", visorScrollback, sizeof(visorScrollback))) {
				visorScrollback[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "visor_compose_agent_id", composeAgent, sizeof(composeAgent))) {
				composeAgent[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "visor_compose_text", composeText, sizeof(composeText))) {
				composeText[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "visor_compose_hint", composeHint, sizeof(composeHint))) {
				composeHint[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "visor_compose_picker", composePicker, sizeof(composePicker))) {
				composePicker[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "security_connector_approval_id",
					securityConnectorId, sizeof(securityConnectorId))) {
				securityConnectorId[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "security_connector_hud",
					securityConnectorHud, sizeof(securityConnectorHud))) {
				securityConnectorHud[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "security_connector_picker",
					securityConnectorPicker, sizeof(securityConnectorPicker))) {
				securityConnectorPicker[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "security_connector_picker_huds",
					securityConnectorPickerHuds, sizeof(securityConnectorPickerHuds))) {
				securityConnectorPickerHuds[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "comms_connector_stage_hud",
					commsConnectorStageHud, sizeof(commsConnectorStageHud))) {
				commsConnectorStageHud[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "comms_connector_stage_intent",
					commsConnectorStageIntent, sizeof(commsConnectorStageIntent))) {
				commsConnectorStageIntent[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "comms_connector_stage_channel",
					commsConnectorStageChannel, sizeof(commsConnectorStageChannel))) {
				commsConnectorStageChannel[0] = '\0';
			}
			if (!officeExtractJsonString(dmBody, "comms_connector_stage_text",
					commsConnectorStageText, sizeof(commsConnectorStageText))) {
				commsConnectorStageText[0] = '\0';
			}
		}
	}

	officePublishPollCache(summary[0] ? summary : NULL, notify[0] ? notify : NULL,
			visorRail[0] ? visorRail : NULL, visorScrollback[0] ? visorScrollback : NULL, attemptUs);

	{
		pthread_mutex_lock(&g_OfficePollCacheMutex);
		g_OfficeVisorComposeAgentIdLen = 0;
		g_OfficeVisorComposeAgentId[0] = '\0';
		g_OfficeVisorComposeTextLen = 0;
		g_OfficeVisorComposeText[0] = '\0';
		g_OfficeVisorComposeHintLen = 0;
		g_OfficeVisorComposeHint[0] = '\0';
		g_OfficeVisorComposePickerLen = 0;
		g_OfficeVisorComposePicker[0] = '\0';
		if (composeAgent[0] && composeText[0]) {
			strncpy(g_OfficeVisorComposeAgentId, composeAgent, sizeof(g_OfficeVisorComposeAgentId) - 1);
			g_OfficeVisorComposeAgentId[sizeof(g_OfficeVisorComposeAgentId) - 1] = '\0';
			g_OfficeVisorComposeAgentIdLen = (s32)strlen(g_OfficeVisorComposeAgentId);
			strncpy(g_OfficeVisorComposeText, composeText, sizeof(g_OfficeVisorComposeText) - 1);
			g_OfficeVisorComposeText[sizeof(g_OfficeVisorComposeText) - 1] = '\0';
			g_OfficeVisorComposeTextLen = (s32)strlen(g_OfficeVisorComposeText);
		}
		if (composeHint[0]) {
			strncpy(g_OfficeVisorComposeHint, composeHint, sizeof(g_OfficeVisorComposeHint) - 1);
			g_OfficeVisorComposeHint[sizeof(g_OfficeVisorComposeHint) - 1] = '\0';
			g_OfficeVisorComposeHintLen = (s32)strlen(g_OfficeVisorComposeHint);
		}
		if (composePicker[0]) {
			strncpy(g_OfficeVisorComposePicker, composePicker, sizeof(g_OfficeVisorComposePicker) - 1);
			g_OfficeVisorComposePicker[sizeof(g_OfficeVisorComposePicker) - 1] = '\0';
			g_OfficeVisorComposePickerLen = (s32)strlen(g_OfficeVisorComposePicker);
		}
		pthread_mutex_unlock(&g_OfficePollCacheMutex);
	}

	{
		char prevApprovalId[OFFICE_SECURITY_CONNECTOR_ID_CAP];

		pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
		prevApprovalId[0] = '\0';
		if (g_OfficeSecurityConnectorApprovalIdLen > 0 && g_OfficeSecurityConnectorApprovalId[0]) {
			strncpy(prevApprovalId, g_OfficeSecurityConnectorApprovalId,
					sizeof(prevApprovalId) - 1);
			prevApprovalId[sizeof(prevApprovalId) - 1] = '\0';
		}
		g_OfficeSecurityConnectorApprovalIdLen = 0;
		g_OfficeSecurityConnectorApprovalId[0] = '\0';
		g_OfficeSecurityConnectorHudLen = 0;
		g_OfficeSecurityConnectorHud[0] = '\0';
		g_OfficeSecurityConnectorPickerCount = 0;
		g_OfficeSecurityConnectorPickerIndex = 0;
		if (securityConnectorPicker[0] && securityConnectorPickerHuds[0]) {
			officeSecurityConnectorParsePicker(securityConnectorPicker, securityConnectorPickerHuds);
		} else if (securityConnectorId[0] && securityConnectorHud[0]) {
			strncpy(g_OfficeSecurityConnectorPickerIds[0], securityConnectorId,
					sizeof(g_OfficeSecurityConnectorPickerIds[0]) - 1);
			g_OfficeSecurityConnectorPickerIds[0][sizeof(g_OfficeSecurityConnectorPickerIds[0]) - 1] = '\0';
			strncpy(g_OfficeSecurityConnectorPickerHuds[0], securityConnectorHud,
					sizeof(g_OfficeSecurityConnectorPickerHuds[0]) - 1);
			g_OfficeSecurityConnectorPickerHuds[0][sizeof(g_OfficeSecurityConnectorPickerHuds[0]) - 1] = '\0';
			g_OfficeSecurityConnectorPickerCount = 1;
			g_OfficeSecurityConnectorPickerIndex = 0;
		}
		if (g_OfficeSecurityConnectorPickerCount > 0) {
			s32 i;

			g_OfficeSecurityConnectorPickerIndex = 0;
			if (prevApprovalId[0]) {
				for (i = 0; i < g_OfficeSecurityConnectorPickerCount; i++) {
					if (!strcmp(g_OfficeSecurityConnectorPickerIds[i], prevApprovalId)) {
						g_OfficeSecurityConnectorPickerIndex = i;
						break;
					}
				}
			}
			officeSecurityConnectorSyncSelected();
		}
		pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
	}

	{
		pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
		g_OfficeCommsConnectorStageHudLen = 0;
		g_OfficeCommsConnectorStageHud[0] = '\0';
		g_OfficeCommsConnectorStageIntentLen = 0;
		g_OfficeCommsConnectorStageIntent[0] = '\0';
		g_OfficeCommsConnectorStageChannelLen = 0;
		g_OfficeCommsConnectorStageChannel[0] = '\0';
		g_OfficeCommsConnectorStageTextLen = 0;
		g_OfficeCommsConnectorStageText[0] = '\0';
		if (commsConnectorStageHud[0] && commsConnectorStageIntent[0]
				&& commsConnectorStageChannel[0] && commsConnectorStageText[0]) {
			strncpy(g_OfficeCommsConnectorStageHud, commsConnectorStageHud,
					sizeof(g_OfficeCommsConnectorStageHud) - 1);
			g_OfficeCommsConnectorStageHud[sizeof(g_OfficeCommsConnectorStageHud) - 1] = '\0';
			g_OfficeCommsConnectorStageHudLen = (s32)strlen(g_OfficeCommsConnectorStageHud);
			strncpy(g_OfficeCommsConnectorStageIntent, commsConnectorStageIntent,
					sizeof(g_OfficeCommsConnectorStageIntent) - 1);
			g_OfficeCommsConnectorStageIntent[sizeof(g_OfficeCommsConnectorStageIntent) - 1] = '\0';
			g_OfficeCommsConnectorStageIntentLen = (s32)strlen(g_OfficeCommsConnectorStageIntent);
			strncpy(g_OfficeCommsConnectorStageChannel, commsConnectorStageChannel,
					sizeof(g_OfficeCommsConnectorStageChannel) - 1);
			g_OfficeCommsConnectorStageChannel[sizeof(g_OfficeCommsConnectorStageChannel) - 1] = '\0';
			g_OfficeCommsConnectorStageChannelLen = (s32)strlen(g_OfficeCommsConnectorStageChannel);
			strncpy(g_OfficeCommsConnectorStageText, commsConnectorStageText,
					sizeof(g_OfficeCommsConnectorStageText) - 1);
			g_OfficeCommsConnectorStageText[sizeof(g_OfficeCommsConnectorStageText) - 1] = '\0';
			g_OfficeCommsConnectorStageTextLen = (s32)strlen(g_OfficeCommsConnectorStageText);
		}
		pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
	}

	if (summary[0]) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] general_summary cached (%d chars)",
				(s32)strlen(summary));
	}
	if (notify[0]) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] dm notification cached (%d chars)",
				(s32)strlen(notify));
	}
	if (visorRail[0]) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] visor rail cached (%d chars)",
				(s32)strlen(visorRail));
	}
	if (visorScrollback[0]) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] visor scrollback cached (%d chars)",
				(s32)strlen(visorScrollback));
	}

	/* R3: diegetic Perfect Menu / desk monitors from Office Service fleet. */
	{
		char fleetBody[OFFICE_HTTP_BODY_CAP];
		char perfectMenu[OFFICE_PERFECT_MENU_CAP];

		perfectMenu[0] = '\0';
		pthread_mutex_lock(&g_OfficePollCacheMutex);
		g_OfficePerfectMenuTextLen = 0;
		g_OfficePerfectMenuText[0] = '\0';
		g_OfficeMonitorCount = 0;
		pthread_mutex_unlock(&g_OfficePollCacheMutex);

		if (officeHttpGetFleet(fleetBody, sizeof(fleetBody))) {
			if (!officeExtractJsonString(fleetBody, "perfect_menu_text", perfectMenu, sizeof(perfectMenu))) {
				perfectMenu[0] = '\0';
			}

			pthread_mutex_lock(&g_OfficePollCacheMutex);
			officeParseFleetMonitors(fleetBody);
			if (perfectMenu[0]) {
				strncpy(g_OfficePerfectMenuText, perfectMenu, sizeof(g_OfficePerfectMenuText) - 1);
				g_OfficePerfectMenuText[sizeof(g_OfficePerfectMenuText) - 1] = '\0';
				g_OfficePerfectMenuTextLen = (s32)strlen(g_OfficePerfectMenuText);
			} else if (g_OfficeMonitorCount > 0) {
				/* Build a pipe overview when the service predates perfect_menu_text. */
				s32 i;
				s32 used = 0;

				g_OfficePerfectMenuText[0] = '\0';
				for (i = 0; i < g_OfficeMonitorCount; i++) {
					s32 n = snprintf(g_OfficePerfectMenuText + used,
							sizeof(g_OfficePerfectMenuText) - (size_t)used,
							"%s%s",
							used > 0 ? " | " : "",
							g_OfficeMonitorTexts[i]);
					if (n <= 0) {
						break;
					}
					used += n;
					if (used >= (s32)sizeof(g_OfficePerfectMenuText) - 1) {
						break;
					}
				}
				g_OfficePerfectMenuTextLen = (s32)strlen(g_OfficePerfectMenuText);
			}
			pthread_mutex_unlock(&g_OfficePollCacheMutex);

			if (g_OfficePerfectMenuTextLen > 0) {
				sysLogPrintf(LOG_NOTE, "[office-bridge] perfect_menu_text cached (%d chars, %d desks)",
						g_OfficePerfectMenuTextLen, g_OfficeMonitorCount);
			}
		}
	}
}

static void officePollThreadEnsureStarted(void)
{
	if (g_OfficePollThreadRunning) {
		return;
	}

	g_OfficePollStop = 0;
	if (pthread_create(&g_OfficePollThread, NULL, officePollThreadMain, NULL) != 0) {
		sysLogPrintf(LOG_ERROR, "[office-bridge] poll pthread_create() failed");
		return;
	}

	g_OfficePollThreadRunning = 1;
	sysLogPrintf(LOG_NOTE, "[office-bridge] background poll thread started");
}

static void *officePollThreadMain(void *arg)
{
	(void)arg;

	while (!g_OfficePollStop) {
		u64 lastAttempt;
		u64 now;

		if (officeHubActive() && g_OfficeServiceEnabled) {
			pthread_mutex_lock(&g_OfficePollCacheMutex);
			lastAttempt = g_OfficeLastAttemptUs;
			pthread_mutex_unlock(&g_OfficePollCacheMutex);

			now = officeNowUs();
			if (lastAttempt == 0 || now - lastAttempt >= OFFICE_POLL_INTERVAL_US) {
				officeFetchPollCache();
			}
		}

		/* Pass 13: drain walk-up POST queue on worker thread (never blocks main thread). */
		officeWalkUpProcessPending();
		/* Pass 21: drain visor compose POST queue on worker thread. */
		officeVisorComposeProcessPending();
		/* Pass 35: drain Security connector approve/deny POST queue. */
		officeSecurityConnectorProcessPending();
		/* Pass 37: drain Comms connector stage dispatch+perform queue. */
		officeCommsConnectorProcessPending();

		usleep(OFFICE_POLL_THREAD_SLEEP_US);
	}

	return NULL;
}

static void officePollThreadStop(void)
{
	if (!g_OfficePollThreadRunning) {
		return;
	}

	g_OfficePollStop = 1;
	pthread_join(g_OfficePollThread, NULL);
	g_OfficePollThreadRunning = 0;
	sysLogPrintf(LOG_NOTE, "[office-bridge] background poll thread stopped");
}

static const char *officeAgentIdForExamineText(u32 text_id)
{
	/* Pass 8: all eight desk agents — G5 + CI examine status_text lang ids. */
	switch (text_id) {
	case OFFICE_EXAMINE_TEXT_DIRECTOR_G5:
	case OFFICE_EXAMINE_TEXT_DIRECTOR_CI:
		return "director";
	case OFFICE_EXAMINE_TEXT_ORCHESTRATOR_G5:
	case OFFICE_EXAMINE_TEXT_ORCHESTRATOR_CI:
		return "orchestrator";
	case OFFICE_EXAMINE_TEXT_RESEARCH_G5:
	case OFFICE_EXAMINE_TEXT_RESEARCH_CI:
		return "research";
	case OFFICE_EXAMINE_TEXT_CODE_G5:
	case OFFICE_EXAMINE_TEXT_CODE_CI:
		return "code";
	case OFFICE_EXAMINE_TEXT_QA_G5:
	case OFFICE_EXAMINE_TEXT_QA_CI:
		return "qa";
	case OFFICE_EXAMINE_TEXT_SECURITY_G5:
	case OFFICE_EXAMINE_TEXT_SECURITY_CI:
		return "security";
	case OFFICE_EXAMINE_TEXT_OPS_G5:
	case OFFICE_EXAMINE_TEXT_OPS_CI:
		return "ops";
	case OFFICE_EXAMINE_TEXT_COMMS_G5:
	case OFFICE_EXAMINE_TEXT_COMMS_CI:
		return "comms";
	default:
		return NULL;
	}
}

static const char *officeWalkUpTextForAgent(const char *agent_id)
{
	/* Mirror WALK_UP_DM_STUB_TEXTS in dm_threads.py (Pass 8). */
	if (!agent_id) {
		return "status?";
	}
	if (!strcmp(agent_id, "director")) {
		return "fleet status?";
	}
	if (!strcmp(agent_id, "orchestrator")) {
		return "thread priority?";
	}
	if (!strcmp(agent_id, "research")) {
		return "status on vault log?";
	}
	if (!strcmp(agent_id, "code")) {
		return "build status?";
	}
	if (!strcmp(agent_id, "qa")) {
		return "regression status?";
	}
	if (!strcmp(agent_id, "security")) {
		return "perimeter clear?";
	}
	if (!strcmp(agent_id, "ops")) {
		return "deploy pipeline status?";
	}
	if (!strcmp(agent_id, "comms")) {
		return "inbox triage status?";
	}
	return "status?";
}

static s32 officeExtractLastAgentMessageText(const char *json, char *out, s32 outCap)
{
	const char *messages;
	const char *cursor;
	const char *lastTextStart = NULL;
	const char *lastTextEnd = NULL;
	const char *fromPos;
	s32 len;

	if (!json || !out || outCap < 2) {
		return 0;
	}

	messages = strstr(json, "\"messages\"");
	if (!messages) {
		return officeExtractJsonString(json, "hud_text", out, outCap);
	}

	cursor = messages;
	while ((fromPos = strstr(cursor, "\"from\"")) != NULL) {
		const char *agentMarker = strstr(fromPos, "\"agent\"");
		const char *textKey;
		const char *textStart;
		const char *textEnd;

		if (!agentMarker || agentMarker - fromPos > 32) {
			cursor = fromPos + 6;
			continue;
		}

		textKey = strstr(fromPos, "\"text\"");
		if (!textKey || textKey - fromPos > 160) {
			cursor = fromPos + 6;
			continue;
		}

		textKey = strchr(textKey, ':');
		if (!textKey) {
			break;
		}
		textKey++;
		while (*textKey == ' ' || *textKey == '\t') {
			textKey++;
		}
		if (*textKey != '"') {
			cursor = fromPos + 6;
			continue;
		}

		textStart = textKey + 1;
		textEnd = textStart;
		while (*textEnd && *textEnd != '"') {
			if (*textEnd == '\\' && textEnd[1]) {
				textEnd += 2;
			} else {
				textEnd++;
			}
		}
		if (*textEnd != '"') {
			break;
		}

		lastTextStart = textStart;
		lastTextEnd = textEnd;
		cursor = textEnd + 1;
	}

	if (!lastTextStart || !lastTextEnd || lastTextEnd <= lastTextStart) {
		return officeExtractJsonString(json, "hud_text", out, outCap);
	}

	len = (s32)(lastTextEnd - lastTextStart);
	if (len <= 0 || len >= outCap) {
		return 0;
	}

	memcpy(out, lastTextStart, (size_t)len);
	out[len] = '\0';
	return 1;
}

/* Worker-only: POST /dm/walk-up and publish tail into mutex-guarded cache. */
static s32 officeFetchWalkUpDmTailWorker(u32 text_id, const char *agent_id)
{
	char body[OFFICE_HTTP_BODY_CAP];
	char reqJson[384];
	char tail[OFFICE_DM_HUD_CAP];
	const char *walk_up_text;
	const u64 attemptUs = officeNowUs();

	if (!agent_id || !agent_id[0]) {
		return 0;
	}

	walk_up_text = officeWalkUpTextForAgent(agent_id);
	snprintf(reqJson, sizeof(reqJson),
			"{\"agent_id\":\"%s\",\"from\":\"human\",\"text\":\"%s\","
			"\"source\":\"z_target\",\"stub_reply\":true}",
			agent_id, walk_up_text);

	if (!officeHttpRequest("POST", "/dm/walk-up", reqJson, body, sizeof(body))) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] POST /dm/walk-up failed (agent=%s)", agent_id);
		return 0;
	}

	if (!officeExtractLastAgentMessageText(body, tail, sizeof(tail))) {
		if (!officeExtractJsonString(body, "hud_text", tail, sizeof(tail))) {
			sysLogPrintf(LOG_NOTE, "[office-bridge] walk-up response missing hud tail");
			return 0;
		}
	}

	if (!tail[0]) {
		return 0;
	}

	pthread_mutex_lock(&g_OfficeWalkUpMutex);
	strncpy(g_OfficeDmHudText, tail, sizeof(g_OfficeDmHudText) - 1);
	g_OfficeDmHudText[sizeof(g_OfficeDmHudText) - 1] = '\0';
	g_OfficeDmHudTextLen = (s32)strlen(g_OfficeDmHudText);
	g_OfficeLastDmAttemptUs = attemptUs;
	g_OfficeLastDmTextId = text_id;
	/* Pass 15: signal main-thread HUD refresh when player still Z-targeting this agent. */
	if (g_OfficeDmWaitChrnum >= 0 && g_OfficeDmWaitTextId == text_id) {
		g_OfficeDmRefreshReady = 1;
	}
	pthread_mutex_unlock(&g_OfficeWalkUpMutex);

	sysLogPrintf(LOG_NOTE, "[office-bridge] dm tail cached (%d chars, agent=%s)",
			(s32)strlen(tail), agent_id);
	return 1;
}

static void officeWalkUpEnqueue(u32 text_id, const char *agent_id)
{
	if (!agent_id || !agent_id[0]) {
		return;
	}

	pthread_mutex_lock(&g_OfficeWalkUpMutex);
	if (g_OfficeWalkUpPending && g_OfficeWalkUpPendingTextId == text_id) {
		pthread_mutex_unlock(&g_OfficeWalkUpMutex);
		return;
	}

	g_OfficeWalkUpPendingTextId = text_id;
	strncpy(g_OfficeWalkUpPendingAgentId, agent_id, sizeof(g_OfficeWalkUpPendingAgentId) - 1);
	g_OfficeWalkUpPendingAgentId[sizeof(g_OfficeWalkUpPendingAgentId) - 1] = '\0';
	g_OfficeWalkUpPending = 1;
	pthread_mutex_unlock(&g_OfficeWalkUpMutex);
}

static void officeWalkUpProcessPending(void)
{
	u32 text_id;
	char agent_id[32];
	s32 pending;

	pthread_mutex_lock(&g_OfficeWalkUpMutex);
	pending = g_OfficeWalkUpPending;
	if (!pending) {
		pthread_mutex_unlock(&g_OfficeWalkUpMutex);
		return;
	}

	text_id = g_OfficeWalkUpPendingTextId;
	strncpy(agent_id, g_OfficeWalkUpPendingAgentId, sizeof(agent_id) - 1);
	agent_id[sizeof(agent_id) - 1] = '\0';
	g_OfficeWalkUpPending = 0;
	pthread_mutex_unlock(&g_OfficeWalkUpMutex);

	officeFetchWalkUpDmTailWorker(text_id, agent_id);
}

/* Worker-only: POST /dm/{agent_id} for visor pause compose (Pass 21). */
static s32 officeFetchVisorComposeWorker(const char *agent_id, const char *text)
{
	char path[96];
	char body[OFFICE_HTTP_BODY_CAP];
	char reqJson[384];
	char tail[OFFICE_DM_HUD_CAP];
	char feedback[OFFICE_VISOR_COMPOSE_FEEDBACK_CAP];

	if (!agent_id || !agent_id[0] || !text || !text[0]) {
		return 0;
	}

	snprintf(path, sizeof(path), "/dm/%s", agent_id);
	snprintf(reqJson, sizeof(reqJson),
			"{\"from\":\"human\",\"text\":\"%s\",\"stub_reply\":true,\"source\":\"visor_pause\"}",
			text);

	if (!officeHttpRequest("POST", path, reqJson, body, sizeof(body))) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] POST %s failed (visor compose)", path);
		return 0;
	}

	feedback[0] = '\0';
	if (officeExtractLastAgentMessageText(body, tail, sizeof(tail)) && tail[0]) {
		snprintf(feedback, sizeof(feedback), "@%s: %s", agent_id, tail);
	} else {
		snprintf(feedback, sizeof(feedback), "Sent to @%s", agent_id);
	}

	pthread_mutex_lock(&g_OfficeVisorComposeMutex);
	strncpy(g_OfficeVisorComposeFeedback, feedback, sizeof(g_OfficeVisorComposeFeedback) - 1);
	g_OfficeVisorComposeFeedback[sizeof(g_OfficeVisorComposeFeedback) - 1] = '\0';
	g_OfficeVisorComposeFeedbackReady = 1;
	pthread_mutex_unlock(&g_OfficeVisorComposeMutex);

	sysLogPrintf(LOG_NOTE, "[office-bridge] visor compose ok (agent=%s)", agent_id);
	return 1;
}

static void officeVisorComposeEnqueue(const char *agent_id, const char *text)
{
	if (!agent_id || !agent_id[0] || !text || !text[0]) {
		return;
	}

	pthread_mutex_lock(&g_OfficeVisorComposeMutex);
	if (g_OfficeVisorComposePending
			&& !strcmp(g_OfficeVisorComposePendingAgentId, agent_id)
			&& !strcmp(g_OfficeVisorComposePendingText, text)) {
		pthread_mutex_unlock(&g_OfficeVisorComposeMutex);
		return;
	}

	strncpy(g_OfficeVisorComposePendingAgentId, agent_id, sizeof(g_OfficeVisorComposePendingAgentId) - 1);
	g_OfficeVisorComposePendingAgentId[sizeof(g_OfficeVisorComposePendingAgentId) - 1] = '\0';
	strncpy(g_OfficeVisorComposePendingText, text, sizeof(g_OfficeVisorComposePendingText) - 1);
	g_OfficeVisorComposePendingText[sizeof(g_OfficeVisorComposePendingText) - 1] = '\0';
	g_OfficeVisorComposePending = 1;
	pthread_mutex_unlock(&g_OfficeVisorComposeMutex);
}

static void officeVisorComposeProcessPending(void)
{
	char agent_id[OFFICE_VISOR_COMPOSE_AGENT_CAP];
	char text[OFFICE_VISOR_COMPOSE_TEXT_CAP];
	s32 pending;

	pthread_mutex_lock(&g_OfficeVisorComposeMutex);
	pending = g_OfficeVisorComposePending;
	if (!pending) {
		pthread_mutex_unlock(&g_OfficeVisorComposeMutex);
		return;
	}

	strncpy(agent_id, g_OfficeVisorComposePendingAgentId, sizeof(agent_id) - 1);
	agent_id[sizeof(agent_id) - 1] = '\0';
	strncpy(text, g_OfficeVisorComposePendingText, sizeof(text) - 1);
	text[sizeof(text) - 1] = '\0';
	g_OfficeVisorComposePending = 0;
	pthread_mutex_unlock(&g_OfficeVisorComposeMutex);

	officeFetchVisorComposeWorker(agent_id, text);
}

static void officeSecurityConnectorSyncSelected(void)
{
	s32 idx;

	if (g_OfficeSecurityConnectorPickerCount <= 0) {
		g_OfficeSecurityConnectorApprovalIdLen = 0;
		g_OfficeSecurityConnectorApprovalId[0] = '\0';
		g_OfficeSecurityConnectorHudLen = 0;
		g_OfficeSecurityConnectorHud[0] = '\0';
		return;
	}

	if (g_OfficeSecurityConnectorPickerIndex < 0
			|| g_OfficeSecurityConnectorPickerIndex >= g_OfficeSecurityConnectorPickerCount) {
		g_OfficeSecurityConnectorPickerIndex = 0;
	}

	idx = g_OfficeSecurityConnectorPickerIndex;
	strncpy(g_OfficeSecurityConnectorApprovalId, g_OfficeSecurityConnectorPickerIds[idx],
			sizeof(g_OfficeSecurityConnectorApprovalId) - 1);
	g_OfficeSecurityConnectorApprovalId[sizeof(g_OfficeSecurityConnectorApprovalId) - 1] = '\0';
	g_OfficeSecurityConnectorApprovalIdLen = (s32)strlen(g_OfficeSecurityConnectorApprovalId);
	strncpy(g_OfficeSecurityConnectorHud, g_OfficeSecurityConnectorPickerHuds[idx],
			sizeof(g_OfficeSecurityConnectorHud) - 1);
	g_OfficeSecurityConnectorHud[sizeof(g_OfficeSecurityConnectorHud) - 1] = '\0';
	g_OfficeSecurityConnectorHudLen = (s32)strlen(g_OfficeSecurityConnectorHud);
}

static void officeSecurityConnectorParsePicker(const char *picker_ids, const char *picker_huds)
{
	char idBuf[OFFICE_SECURITY_CONNECTOR_PICKER_CAP];
	char *idLine;
	char *idSave;
	const char *hudPos;
	s32 count;

	g_OfficeSecurityConnectorPickerCount = 0;
	g_OfficeSecurityConnectorPickerIndex = 0;

	if (!picker_ids || !picker_ids[0] || !picker_huds || !picker_huds[0]) {
		return;
	}

	strncpy(idBuf, picker_ids, sizeof(idBuf) - 1);
	idBuf[sizeof(idBuf) - 1] = '\0';
	idLine = strtok_r(idBuf, "|", &idSave);
	hudPos = picker_huds;
	count = 0;

	while (idLine && hudPos && *hudPos && count < OFFICE_SECURITY_CONNECTOR_PICKER_MAX) {
		const char *hudSep;
		s32 hudLen;

		if (!idLine[0]) {
			idLine = strtok_r(NULL, "|", &idSave);
			continue;
		}

		hudSep = strstr(hudPos, "||");
		hudLen = hudSep ? (s32)(hudSep - hudPos) : (s32)strlen(hudPos);
		if (hudLen <= 0 || hudLen >= OFFICE_SECURITY_CONNECTOR_HUD_CAP) {
			break;
		}

		strncpy(g_OfficeSecurityConnectorPickerIds[count], idLine,
				sizeof(g_OfficeSecurityConnectorPickerIds[0]) - 1);
		g_OfficeSecurityConnectorPickerIds[count][sizeof(g_OfficeSecurityConnectorPickerIds[0]) - 1] = '\0';
		memcpy(g_OfficeSecurityConnectorPickerHuds[count], hudPos, (size_t)hudLen);
		g_OfficeSecurityConnectorPickerHuds[count][hudLen] = '\0';
		count++;

		if (!hudSep) {
			break;
		}
		hudPos = hudSep + 2;
		idLine = strtok_r(NULL, "|", &idSave);
	}

	g_OfficeSecurityConnectorPickerCount = count;
}

static s32 officeSecurityConnectorIsSecurityText(u32 text_id)
{
	return text_id == OFFICE_EXAMINE_TEXT_SECURITY_G5
		|| text_id == OFFICE_EXAMINE_TEXT_SECURITY_CI;
}

/* Worker-only: POST /approvals/{id}/approve or /deny (Pass 35). */
static s32 officeFetchSecurityConnectorActionWorker(const char *approval_id, s32 approve)
{
	char path[128];
	char body[OFFICE_HTTP_BODY_CAP];
	char reqJson[128];
	char feedback[OFFICE_SECURITY_CONNECTOR_FEEDBACK_CAP];

	if (!approval_id || !approval_id[0]) {
		return 0;
	}

	snprintf(path, sizeof(path), "/approvals/%s/%s", approval_id, approve ? "approve" : "deny");
	snprintf(reqJson, sizeof(reqJson), "{\"decided_by\":\"security\"}");

	if (!officeHttpRequest("POST", path, reqJson, body, sizeof(body))) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] POST %s failed (Security connector)", path);
		snprintf(feedback, sizeof(feedback),
				approve ? "Connector approval failed" : "Connector deny failed");
	} else if (approve) {
		snprintf(feedback, sizeof(feedback), "Connector approved");
	} else {
		snprintf(feedback, sizeof(feedback), "Connector denied");
	}

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	strncpy(g_OfficeSecurityConnectorFeedback, feedback, sizeof(g_OfficeSecurityConnectorFeedback) - 1);
	g_OfficeSecurityConnectorFeedback[sizeof(g_OfficeSecurityConnectorFeedback) - 1] = '\0';
	g_OfficeSecurityConnectorFeedbackReady = 1;
	g_OfficeSecurityConnectorApprovalIdLen = 0;
	g_OfficeSecurityConnectorApprovalId[0] = '\0';
	g_OfficeSecurityConnectorHudLen = 0;
	g_OfficeSecurityConnectorHud[0] = '\0';
	g_OfficeSecurityConnectorPickerCount = 0;
	g_OfficeSecurityConnectorPickerIndex = 0;
	g_OfficeSecurityConnectorBusy = 0;
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);

	sysLogPrintf(LOG_NOTE, "[office-bridge] Security connector %s ok (id=%s)",
			approve ? "approve" : "deny", approval_id);
	return 1;
}

static void officeSecurityConnectorEnqueue(const char *approval_id, s32 approve)
{
	if (!approval_id || !approval_id[0]) {
		return;
	}

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	if (g_OfficeSecurityConnectorBusy || g_OfficeSecurityConnectorActionPending) {
		pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
		return;
	}

	strncpy(g_OfficeSecurityConnectorPendingApprovalId, approval_id,
			sizeof(g_OfficeSecurityConnectorPendingApprovalId) - 1);
	g_OfficeSecurityConnectorPendingApprovalId[sizeof(g_OfficeSecurityConnectorPendingApprovalId) - 1] = '\0';
	g_OfficeSecurityConnectorPendingApprove = approve ? 1 : 0;
	g_OfficeSecurityConnectorActionPending = 1;
	g_OfficeSecurityConnectorBusy = 1;
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
}

static void officeSecurityConnectorProcessPending(void)
{
	char approval_id[OFFICE_SECURITY_CONNECTOR_ID_CAP];
	s32 approve;
	s32 pending;

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	pending = g_OfficeSecurityConnectorActionPending;
	if (!pending) {
		pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
		return;
	}

	strncpy(approval_id, g_OfficeSecurityConnectorPendingApprovalId, sizeof(approval_id) - 1);
	approval_id[sizeof(approval_id) - 1] = '\0';
	approve = g_OfficeSecurityConnectorPendingApprove;
	g_OfficeSecurityConnectorActionPending = 0;
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);

	officeFetchSecurityConnectorActionWorker(approval_id, approve);
}

static s32 officeCommsConnectorIsCommsText(u32 text_id)
{
	return text_id == OFFICE_EXAMINE_TEXT_COMMS_G5
		|| text_id == OFFICE_EXAMINE_TEXT_COMMS_CI;
}

/* Worker-only: POST /dispatch then /tasks/{id}/perform slack.post_message (Pass 37). */
static s32 officeFetchCommsConnectorStageWorker(const char *intent, const char *channel, const char *text)
{
	char body[OFFICE_HTTP_BODY_CAP];
	char reqJson[384];
	char performJson[512];
	char path[128];
	char taskId[OFFICE_SECURITY_CONNECTOR_ID_CAP];
	char feedback[OFFICE_COMMS_CONNECTOR_FEEDBACK_CAP];

	if (!intent || !intent[0] || !channel || !channel[0] || !text || !text[0]) {
		return 0;
	}

	snprintf(reqJson, sizeof(reqJson),
			"{\"agent_id\":\"comms\",\"intent\":\"%s\",\"created_by\":\"game\"}",
			intent);

	if (!officeHttpRequest("POST", "/dispatch", reqJson, body, sizeof(body))) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] POST /dispatch failed (Comms connector stage)");
		snprintf(feedback, sizeof(feedback), "Comms stage failed");
		goto publish_feedback;
	}

	if (!officeExtractJsonString(body, "id", taskId, sizeof(taskId))) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] dispatch response missing id (Comms connector stage)");
		snprintf(feedback, sizeof(feedback), "Comms stage failed");
		goto publish_feedback;
	}

	snprintf(path, sizeof(path), "/tasks/%s/perform", taskId);
	snprintf(performJson, sizeof(performJson),
			"{\"actions\":[{\"connector\":\"slack\",\"action\":\"post_message\","
			"\"args\":{\"channel\":\"%s\",\"text\":\"%s\"}}]}",
			channel, text);

	if (!officeHttpRequest("POST", path, performJson, body, sizeof(body))) {
		sysLogPrintf(LOG_NOTE, "[office-bridge] POST %s failed (Comms connector stage)", path);
		snprintf(feedback, sizeof(feedback), "Comms stage failed");
		goto publish_feedback;
	}

	if (strstr(body, "awaiting_approval")) {
		snprintf(feedback, sizeof(feedback), "Staged — approve at Security");
	} else {
		snprintf(feedback, sizeof(feedback), "Comms stage failed");
	}

publish_feedback:
	pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
	strncpy(g_OfficeCommsConnectorFeedback, feedback, sizeof(g_OfficeCommsConnectorFeedback) - 1);
	g_OfficeCommsConnectorFeedback[sizeof(g_OfficeCommsConnectorFeedback) - 1] = '\0';
	g_OfficeCommsConnectorFeedbackReady = 1;
	g_OfficeCommsConnectorBusy = 0;
	pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);

	sysLogPrintf(LOG_NOTE, "[office-bridge] Comms connector stage ok (channel=%s)", channel);
	return 1;
}

static void officeCommsConnectorEnqueue(const char *intent, const char *channel, const char *text)
{
	if (!intent || !intent[0] || !channel || !channel[0] || !text || !text[0]) {
		return;
	}

	pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
	if (g_OfficeCommsConnectorBusy || g_OfficeCommsConnectorStagePending) {
		pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
		return;
	}

	strncpy(g_OfficeCommsConnectorPendingIntent, intent,
			sizeof(g_OfficeCommsConnectorPendingIntent) - 1);
	g_OfficeCommsConnectorPendingIntent[sizeof(g_OfficeCommsConnectorPendingIntent) - 1] = '\0';
	strncpy(g_OfficeCommsConnectorPendingChannel, channel,
			sizeof(g_OfficeCommsConnectorPendingChannel) - 1);
	g_OfficeCommsConnectorPendingChannel[sizeof(g_OfficeCommsConnectorPendingChannel) - 1] = '\0';
	strncpy(g_OfficeCommsConnectorPendingText, text,
			sizeof(g_OfficeCommsConnectorPendingText) - 1);
	g_OfficeCommsConnectorPendingText[sizeof(g_OfficeCommsConnectorPendingText) - 1] = '\0';
	g_OfficeCommsConnectorStagePending = 1;
	g_OfficeCommsConnectorBusy = 1;
	pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
}

static void officeCommsConnectorProcessPending(void)
{
	char intent[OFFICE_COMMS_CONNECTOR_INTENT_CAP];
	char channel[OFFICE_COMMS_CONNECTOR_CHANNEL_CAP];
	char text[OFFICE_COMMS_CONNECTOR_TEXT_CAP];
	s32 pending;

	pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
	pending = g_OfficeCommsConnectorStagePending;
	if (!pending) {
		pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
		return;
	}

	strncpy(intent, g_OfficeCommsConnectorPendingIntent, sizeof(intent) - 1);
	intent[sizeof(intent) - 1] = '\0';
	strncpy(channel, g_OfficeCommsConnectorPendingChannel, sizeof(channel) - 1);
	channel[sizeof(channel) - 1] = '\0';
	strncpy(text, g_OfficeCommsConnectorPendingText, sizeof(text) - 1);
	text[sizeof(text) - 1] = '\0';
	g_OfficeCommsConnectorStagePending = 0;
	pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);

	officeFetchCommsConnectorStageWorker(intent, channel, text);
}

static void officeVisorComposeDoSubmit(const char *agent_id, const char *text)
{
	const u64 now = officeNowUs();

	if (!agent_id || !agent_id[0] || !text || !text[0]) {
		return;
	}

	if (!officeHubActive() || !g_OfficeServiceEnabled) {
		return;
	}

	if (g_OfficeLastVisorComposeUs != 0
			&& now - g_OfficeLastVisorComposeUs < OFFICE_VISOR_COMPOSE_COOLDOWN_US) {
		return;
	}

	officePollThreadEnsureStarted();
	g_OfficeLastVisorComposeUs = now;
	officeVisorComposeEnqueue(agent_id, text);
}

static void officeVisorComposeParsePicker(void)
{
	char buf[OFFICE_VISOR_COMPOSE_PICKER_CAP];
	char *line;
	char *saveptr;
	s32 i;

	g_OfficeVisorComposePickerCount = 0;
	g_OfficeVisorComposePickerIndex = 0;

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficeVisorComposePickerLen > 0 && g_OfficeVisorComposePicker[0]) {
		strncpy(buf, g_OfficeVisorComposePicker, sizeof(buf) - 1);
		buf[sizeof(buf) - 1] = '\0';
	} else {
		buf[0] = '\0';
	}
	pthread_mutex_unlock(&g_OfficePollCacheMutex);

	if (buf[0]) {
		line = strtok_r(buf, "|", &saveptr);
		while (line && g_OfficeVisorComposePickerCount < OFFICE_VISOR_COMPOSE_PICKER_MAX) {
			if (line[0]) {
				strncpy(g_OfficeVisorComposePickerAgents[g_OfficeVisorComposePickerCount], line,
						sizeof(g_OfficeVisorComposePickerAgents[0]) - 1);
				g_OfficeVisorComposePickerAgents[g_OfficeVisorComposePickerCount]
						[sizeof(g_OfficeVisorComposePickerAgents[0]) - 1] = '\0';
				g_OfficeVisorComposePickerCount++;
			}
			line = strtok_r(NULL, "|", &saveptr);
		}
	}

	if (g_OfficeVisorComposePickerCount == 0 && g_OfficeVisorComposeInputAgentId[0]) {
		strncpy(g_OfficeVisorComposePickerAgents[0], g_OfficeVisorComposeInputAgentId,
				sizeof(g_OfficeVisorComposePickerAgents[0]) - 1);
		g_OfficeVisorComposePickerAgents[0][sizeof(g_OfficeVisorComposePickerAgents[0]) - 1] = '\0';
		g_OfficeVisorComposePickerCount = 1;
	}

	for (i = 0; i < g_OfficeVisorComposePickerCount; i++) {
		if (!strcmp(g_OfficeVisorComposePickerAgents[i], g_OfficeVisorComposeInputAgentId)) {
			g_OfficeVisorComposePickerIndex = i;
			return;
		}
	}

	g_OfficeVisorComposePickerIndex = 0;
	if (g_OfficeVisorComposePickerCount > 0) {
		strncpy(g_OfficeVisorComposeInputAgentId, g_OfficeVisorComposePickerAgents[0],
				sizeof(g_OfficeVisorComposeInputAgentId) - 1);
		g_OfficeVisorComposeInputAgentId[sizeof(g_OfficeVisorComposeInputAgentId) - 1] = '\0';
	}
}

void officeServiceBridgeInit(void)
{
	const char *env;

	/* CLI may not be ready in PD_CONSTRUCTOR — re-arm here. */
	env = getenv("BOOT_OPEN_CONSOLE");
	if ((env && env[0] && env[0] != '0') || sysArgCheck("--boot-open-console")) {
		if (!g_OfficeBootOpenConsole) {
			sysLogPrintf(LOG_NOTE, "[office-bridge] BOOT_OPEN_CONSOLE armed");
		}
		g_OfficeBootOpenConsole = 1;
	}

	g_OfficePollStop = 0;
	g_OfficePollThreadRunning = 0;
	g_OfficeBootOpenDone = 0;
	g_OfficeBootOpenWaitTicks = 0;
	g_OfficeLiveSummary[0] = '\0';
	g_OfficeLiveSummaryLen = 0;
	g_OfficeDmHudText[0] = '\0';
	g_OfficeDmHudTextLen = 0;
	g_OfficeVisorNotification[0] = '\0';
	g_OfficeVisorNotificationLen = 0;
	g_OfficeVisorRail[0] = '\0';
	g_OfficeVisorRailLen = 0;
	g_OfficeVisorScrollback[0] = '\0';
	g_OfficeVisorScrollbackLen = 0;
	g_OfficeVisorComposeAgentId[0] = '\0';
	g_OfficeVisorComposeAgentIdLen = 0;
	g_OfficeVisorComposeText[0] = '\0';
	g_OfficeVisorComposeTextLen = 0;
	g_OfficeVisorComposeHint[0] = '\0';
	g_OfficeVisorComposeHintLen = 0;
	g_OfficeVisorComposePicker[0] = '\0';
	g_OfficeVisorComposePickerLen = 0;
	g_OfficeLastFetchUs = 0;
	g_OfficeLastAttemptUs = 0;
	g_OfficeLastDmAttemptUs = 0;
	g_OfficeLastDmTextId = 0;
	g_OfficeWalkUpPendingTextId = 0;
	g_OfficeWalkUpPendingAgentId[0] = '\0';
	g_OfficeWalkUpPending = 0;
	g_OfficeDmWaitChrnum = -1;
	g_OfficeDmWaitTextId = 0;
	g_OfficeDmRefreshReady = 0;
	g_OfficeVisorComposePending = 0;
	g_OfficeVisorComposePendingAgentId[0] = '\0';
	g_OfficeVisorComposePendingText[0] = '\0';
	g_OfficeVisorComposeFeedback[0] = '\0';
	g_OfficeVisorComposeFeedbackReady = 0;
	g_OfficeLastVisorComposeUs = 0;
	g_OfficeVisorComposeInputActive = 0;
	g_OfficeVisorComposeInputUser[0] = '\0';
	g_OfficeVisorComposeInputCursor = 0;
	g_OfficeVisorComposeInputAgentId[0] = '\0';
	g_OfficeVisorComposeInputHud[0] = '\0';
	g_OfficeVisorComposeInputLastHud[0] = '\0';
	g_OfficeVisorComposePickerCount = 0;
	g_OfficeVisorComposePickerIndex = 0;
	g_OfficeSecurityConnectorApprovalId[0] = '\0';
	g_OfficeSecurityConnectorApprovalIdLen = 0;
	g_OfficeSecurityConnectorHud[0] = '\0';
	g_OfficeSecurityConnectorHudLen = 0;
	g_OfficeSecurityConnectorActionPending = 0;
	g_OfficeSecurityConnectorPendingApprovalId[0] = '\0';
	g_OfficeSecurityConnectorPendingApprove = 0;
	g_OfficeSecurityConnectorFeedback[0] = '\0';
	g_OfficeSecurityConnectorFeedbackReady = 0;
	g_OfficeSecurityConnectorWaitChrnum = -1;
	g_OfficeSecurityConnectorWaitTextId = 0;
	g_OfficeSecurityConnectorBusy = 0;
	g_OfficeSecurityConnectorPickerCount = 0;
	g_OfficeSecurityConnectorPickerIndex = 0;
	g_OfficeCommsConnectorStageHud[0] = '\0';
	g_OfficeCommsConnectorStageHudLen = 0;
	g_OfficeCommsConnectorStageIntent[0] = '\0';
	g_OfficeCommsConnectorStageIntentLen = 0;
	g_OfficeCommsConnectorStageChannel[0] = '\0';
	g_OfficeCommsConnectorStageChannelLen = 0;
	g_OfficeCommsConnectorStageText[0] = '\0';
	g_OfficeCommsConnectorStageTextLen = 0;
	g_OfficeCommsConnectorStagePending = 0;
	g_OfficeCommsConnectorPendingIntent[0] = '\0';
	g_OfficeCommsConnectorPendingChannel[0] = '\0';
	g_OfficeCommsConnectorPendingText[0] = '\0';
	g_OfficeCommsConnectorFeedback[0] = '\0';
	g_OfficeCommsConnectorFeedbackReady = 0;
	g_OfficeCommsConnectorWaitChrnum = -1;
	g_OfficeCommsConnectorWaitTextId = 0;
	g_OfficeCommsConnectorBusy = 0;
	g_OfficeLastCommsConnectorStageUs = 0;
}

void officeServiceBridgeShutdown(void)
{
	officePollThreadStop();

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	g_OfficeLiveSummaryLen = 0;
	g_OfficeLiveSummary[0] = '\0';
	g_OfficeVisorNotificationLen = 0;
	g_OfficeVisorNotification[0] = '\0';
	g_OfficeVisorRailLen = 0;
	g_OfficeVisorRail[0] = '\0';
	g_OfficeVisorScrollbackLen = 0;
	g_OfficeVisorScrollback[0] = '\0';
	g_OfficeVisorComposeAgentIdLen = 0;
	g_OfficeVisorComposeAgentId[0] = '\0';
	g_OfficeVisorComposeTextLen = 0;
	g_OfficeVisorComposeText[0] = '\0';
	g_OfficeVisorComposeHintLen = 0;
	g_OfficeVisorComposeHint[0] = '\0';
	g_OfficeVisorComposePickerLen = 0;
	g_OfficeVisorComposePicker[0] = '\0';
	g_OfficeLastFetchUs = 0;
	g_OfficeLastAttemptUs = 0;
	pthread_mutex_unlock(&g_OfficePollCacheMutex);

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	g_OfficeSecurityConnectorApprovalIdLen = 0;
	g_OfficeSecurityConnectorApprovalId[0] = '\0';
	g_OfficeSecurityConnectorHudLen = 0;
	g_OfficeSecurityConnectorHud[0] = '\0';
	g_OfficeSecurityConnectorActionPending = 0;
	g_OfficeSecurityConnectorPendingApprovalId[0] = '\0';
	g_OfficeSecurityConnectorFeedbackReady = 0;
	g_OfficeSecurityConnectorFeedback[0] = '\0';
	g_OfficeSecurityConnectorBusy = 0;
	g_OfficeSecurityConnectorWaitChrnum = -1;
	g_OfficeSecurityConnectorWaitTextId = 0;
	g_OfficeSecurityConnectorPickerCount = 0;
	g_OfficeSecurityConnectorPickerIndex = 0;
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);

	pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
	g_OfficeCommsConnectorStageHudLen = 0;
	g_OfficeCommsConnectorStageHud[0] = '\0';
	g_OfficeCommsConnectorStageIntentLen = 0;
	g_OfficeCommsConnectorStageIntent[0] = '\0';
	g_OfficeCommsConnectorStageChannelLen = 0;
	g_OfficeCommsConnectorStageChannel[0] = '\0';
	g_OfficeCommsConnectorStageTextLen = 0;
	g_OfficeCommsConnectorStageText[0] = '\0';
	g_OfficeCommsConnectorStagePending = 0;
	g_OfficeCommsConnectorPendingIntent[0] = '\0';
	g_OfficeCommsConnectorPendingChannel[0] = '\0';
	g_OfficeCommsConnectorPendingText[0] = '\0';
	g_OfficeCommsConnectorFeedbackReady = 0;
	g_OfficeCommsConnectorFeedback[0] = '\0';
	g_OfficeCommsConnectorBusy = 0;
	g_OfficeCommsConnectorWaitChrnum = -1;
	g_OfficeCommsConnectorWaitTextId = 0;
	g_OfficeLastCommsConnectorStageUs = 0;
	pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);

	pthread_mutex_lock(&g_OfficeVisorComposeMutex);
	g_OfficeVisorComposePending = 0;
	g_OfficeVisorComposePendingAgentId[0] = '\0';
	g_OfficeVisorComposePendingText[0] = '\0';
	g_OfficeVisorComposeFeedback[0] = '\0';
	g_OfficeVisorComposeFeedbackReady = 0;
	g_OfficeLastVisorComposeUs = 0;
	pthread_mutex_unlock(&g_OfficeVisorComposeMutex);

	g_OfficeVisorComposeInputActive = 0;
	g_OfficeVisorComposeInputUser[0] = '\0';
	g_OfficeVisorComposeInputCursor = 0;
	g_OfficeVisorComposeInputAgentId[0] = '\0';
	g_OfficeVisorComposePickerCount = 0;
	g_OfficeVisorComposePickerIndex = 0;
	inputStopTextInput();

	pthread_mutex_lock(&g_OfficeWalkUpMutex);
	g_OfficeDmHudTextLen = 0;
	g_OfficeDmHudText[0] = '\0';
	g_OfficeLastDmAttemptUs = 0;
	g_OfficeLastDmTextId = 0;
	g_OfficeWalkUpPendingTextId = 0;
	g_OfficeWalkUpPendingAgentId[0] = '\0';
	g_OfficeWalkUpPending = 0;
	g_OfficeDmWaitChrnum = -1;
	g_OfficeDmWaitTextId = 0;
	g_OfficeDmRefreshReady = 0;
	pthread_mutex_unlock(&g_OfficeWalkUpMutex);
}

void officeServiceBridgeTrackDmHudWait(s16 chrnum, u32 text_id)
{
	pthread_mutex_lock(&g_OfficeWalkUpMutex);
	g_OfficeDmWaitChrnum = chrnum;
	g_OfficeDmWaitTextId = text_id;
	g_OfficeDmRefreshReady = 0;
	pthread_mutex_unlock(&g_OfficeWalkUpMutex);
}

void officeServiceBridgeClearDmHudWait(void)
{
	pthread_mutex_lock(&g_OfficeWalkUpMutex);
	g_OfficeDmWaitChrnum = -1;
	g_OfficeDmWaitTextId = 0;
	g_OfficeDmRefreshReady = 0;
	pthread_mutex_unlock(&g_OfficeWalkUpMutex);
}

s32 officeServiceBridgeTryConsumeDmHudRefresh(s16 chrnum, const char **out_tail)
{
	const char *tail = NULL;
	s32 ready = 0;

	if (!out_tail || chrnum < 0) {
		return 0;
	}

	pthread_mutex_lock(&g_OfficeWalkUpMutex);
	if (g_OfficeDmRefreshReady && g_OfficeDmWaitChrnum == chrnum
			&& g_OfficeDmHudTextLen > 0 && g_OfficeDmHudText[0]) {
		tail = g_OfficeDmHudText;
		ready = 1;
		g_OfficeDmRefreshReady = 0;
		g_OfficeDmWaitChrnum = -1;
		g_OfficeDmWaitTextId = 0;
	}
	pthread_mutex_unlock(&g_OfficeWalkUpMutex);

	if (ready) {
		*out_tail = tail;
	}
	return ready;
}

void officeServiceBridgeRefreshIfStale(void)
{
	/* Pass 11: poll cache is refreshed by background thread; main thread never blocks on HTTP. */
	if (!officeHubActive() || !g_OfficeServiceEnabled) {
		return;
	}

	officePollThreadEnsureStarted();
}

/* Same open path as lobby console (Z) in propobjInteract — no walk required. */
static void officeMaybeBootOpenPerfectMenu(void)
{
	const char *menu_text;
	char buf[768];
	char *line;
	char *saveptr;

	if (!g_OfficeBootOpenConsole || g_OfficeBootOpenDone) {
		return;
	}
	if (!officeHubActive()) {
		return;
	}
	if (!g_Vars.currentplayer || !g_Vars.currentplayer->prop) {
		return;
	}
	if (menuGetRoot() != 0) {
		return;
	}

	g_OfficeBootOpenWaitTicks++;
	/* Prefer live fleet text; wait ~2.5s so menu/font textures settle (early open CI4 SEGV). */
	menu_text = officeServiceBridgePerfectMenuText();
	if ((!menu_text || !menu_text[0]) && g_OfficeBootOpenWaitTicks < 180) {
		return;
	}
	if (g_OfficeBootOpenWaitTicks < 150) {
		return;
	}

	officeServiceBridgeRefreshIfStale();
	func0f0f85e0(&g_OfficePerfectMenuDialog, MENUROOT_MAINMENU);
	g_OfficeBootOpenDone = 1;
	sysLogPrintf(LOG_NOTE, "[office-bridge] BOOT_OPEN_CONSOLE: Perfect Menu dialog open");

	menu_text = officeServiceBridgePerfectMenuText();
	if (!menu_text || !menu_text[0]) {
		return;
	}

	strncpy(buf, menu_text, sizeof(buf) - 1);
	buf[sizeof(buf) - 1] = '\0';
	line = strtok_r(buf, "|", &saveptr);
	while (line) {
		while (*line == ' ') {
			line++;
		}
		if (line[0]) {
			hudmsgCreate(line, HUDMSGTYPE_DEFAULT);
		}
		line = strtok_r(NULL, "|", &saveptr);
	}
}

void officeServiceBridgeTick(void)
{
	if (officeHubActive() && g_OfficeServiceEnabled) {
		officePollThreadEnsureStarted();
	}

	officeMaybeBootOpenPerfectMenu();
}

const char *officeServiceBridgeGetLiveSummary(void)
{
	const char *live = NULL;

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficeLiveSummaryLen > 0 && g_OfficeLiveSummary[0]) {
		live = g_OfficeLiveSummary;
	}
	pthread_mutex_unlock(&g_OfficePollCacheMutex);
	return live;
}

const char *officeServiceBridgePerfectMenuText(void)
{
	const char *text = NULL;

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficePerfectMenuTextLen > 0 && g_OfficePerfectMenuText[0]) {
		text = g_OfficePerfectMenuText;
	}
	pthread_mutex_unlock(&g_OfficePollCacheMutex);
	return text;
}

const char *officeServiceBridgeMonitorText(const char *agent_id)
{
	const char *text = NULL;
	s32 i;

	if (!agent_id || !agent_id[0]) {
		return NULL;
	}

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	for (i = 0; i < g_OfficeMonitorCount; i++) {
		if (!strcmp(g_OfficeMonitorAgentIds[i], agent_id)) {
			if (g_OfficeMonitorTexts[i][0]) {
				text = g_OfficeMonitorTexts[i];
			}
			break;
		}
	}
	pthread_mutex_unlock(&g_OfficePollCacheMutex);
	return text;
}

const char *officeServiceBridgeVisorNotificationText(void)
{
	const char *note = NULL;

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficeVisorNotificationLen > 0 && g_OfficeVisorNotification[0]) {
		note = g_OfficeVisorNotification;
	}
	pthread_mutex_unlock(&g_OfficePollCacheMutex);
	return note;
}

/* Pass 14: pipe-delimited DM thread rail from GET /dm (split on '|' for HUD lines). */
const char *officeServiceBridgeVisorRailText(void)
{
	const char *rail = NULL;

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficeVisorRailLen > 0 && g_OfficeVisorRail[0]) {
		rail = g_OfficeVisorRail;
	}
	pthread_mutex_unlock(&g_OfficePollCacheMutex);
	return rail;
}

/* Pass 17: pipe-delimited DM message scrollback from GET /dm (split on '|' for HUD lines). */
const char *officeServiceBridgeVisorScrollbackText(void)
{
	const char *scroll = NULL;

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficeVisorScrollbackLen > 0 && g_OfficeVisorScrollback[0]) {
		scroll = g_OfficeVisorScrollback;
	}
	pthread_mutex_unlock(&g_OfficePollCacheMutex);
	return scroll;
}

const char *officeServiceBridgeVisorComposeHintText(void)
{
	const char *hint = NULL;

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficeVisorComposeHintLen > 0 && g_OfficeVisorComposeHint[0]) {
		hint = g_OfficeVisorComposeHint;
	}
	pthread_mutex_unlock(&g_OfficePollCacheMutex);
	return hint;
}

void officeServiceBridgeVisorComposeSubmit(void)
{
	char agent_id[OFFICE_VISOR_COMPOSE_AGENT_CAP];
	char text[OFFICE_VISOR_COMPOSE_TEXT_CAP];

	if (!officeHubActive() || !g_OfficeServiceEnabled) {
		return;
	}

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficeVisorComposeAgentIdLen <= 0 || g_OfficeVisorComposeTextLen <= 0) {
		pthread_mutex_unlock(&g_OfficePollCacheMutex);
		return;
	}
	strncpy(agent_id, g_OfficeVisorComposeAgentId, sizeof(agent_id) - 1);
	agent_id[sizeof(agent_id) - 1] = '\0';
	strncpy(text, g_OfficeVisorComposeText, sizeof(text) - 1);
	text[sizeof(text) - 1] = '\0';
	pthread_mutex_unlock(&g_OfficePollCacheMutex);

	officeVisorComposeDoSubmit(agent_id, text);
}

void officeServiceBridgeVisorComposeBeginInput(void)
{
	if (!officeHubActive() || !g_OfficeServiceEnabled) {
		return;
	}

	pthread_mutex_lock(&g_OfficePollCacheMutex);
	if (g_OfficeVisorComposeAgentIdLen <= 0 || !g_OfficeVisorComposeAgentId[0]) {
		pthread_mutex_unlock(&g_OfficePollCacheMutex);
		return;
	}
	strncpy(g_OfficeVisorComposeInputAgentId, g_OfficeVisorComposeAgentId,
			sizeof(g_OfficeVisorComposeInputAgentId) - 1);
	g_OfficeVisorComposeInputAgentId[sizeof(g_OfficeVisorComposeInputAgentId) - 1] = '\0';
	pthread_mutex_unlock(&g_OfficePollCacheMutex);

	g_OfficeVisorComposeInputUser[0] = '\0';
	g_OfficeVisorComposeInputCursor = 0;
	g_OfficeVisorComposeInputHud[0] = '\0';
	g_OfficeVisorComposeInputLastHud[0] = '\0';
	inputClearLastKey();
	inputClearLastTextChar();
	inputStartTextInput();
	g_OfficeVisorComposeInputActive = 1;
	officeVisorComposeParsePicker();
}

void officeServiceBridgeVisorComposeCancelInput(void)
{
	if (!g_OfficeVisorComposeInputActive) {
		return;
	}

	g_OfficeVisorComposeInputActive = 0;
	g_OfficeVisorComposeInputUser[0] = '\0';
	g_OfficeVisorComposeInputCursor = 0;
	g_OfficeVisorComposeInputAgentId[0] = '\0';
	g_OfficeVisorComposeInputHud[0] = '\0';
	g_OfficeVisorComposeInputLastHud[0] = '\0';
	g_OfficeVisorComposePickerCount = 0;
	g_OfficeVisorComposePickerIndex = 0;
	inputStopTextInput();
}

s32 officeServiceBridgeVisorComposeInputActive(void)
{
	return g_OfficeVisorComposeInputActive ? 1 : 0;
}

s32 officeServiceBridgeVisorComposeInputStep(const char **out_hud_line)
{
	char prefixed[OFFICE_VISOR_COMPOSE_TEXT_CAP];
	s32 result;

	if (out_hud_line) {
		*out_hud_line = NULL;
	}

	if (!g_OfficeVisorComposeInputActive) {
		return 0;
	}

	if (!g_OfficeVisorComposeInputAgentId[0]) {
		officeServiceBridgeVisorComposeCancelInput();
		return -1;
	}

	{
		const s32 tab_key = inputGetLastKey();
		if (tab_key == OFFICE_VK_TAB && g_OfficeVisorComposePickerCount > 1) {
			inputClearLastKey();
			inputClearLastTextChar();
			g_OfficeVisorComposePickerIndex =
					(g_OfficeVisorComposePickerIndex + 1) % g_OfficeVisorComposePickerCount;
			strncpy(g_OfficeVisorComposeInputAgentId,
					g_OfficeVisorComposePickerAgents[g_OfficeVisorComposePickerIndex],
					sizeof(g_OfficeVisorComposeInputAgentId) - 1);
			g_OfficeVisorComposeInputAgentId[sizeof(g_OfficeVisorComposeInputAgentId) - 1] = '\0';
			snprintf(g_OfficeVisorComposeInputHud, sizeof(g_OfficeVisorComposeInputHud),
					"> @%s: %s", g_OfficeVisorComposeInputAgentId, g_OfficeVisorComposeInputUser);
			if (out_hud_line) {
				*out_hud_line = g_OfficeVisorComposeInputHud;
			}
			return 0;
		}
	}

	result = inputTextHandler(g_OfficeVisorComposeInputUser,
			OFFICE_VISOR_COMPOSE_INPUT_USER_CAP - 1,
			&g_OfficeVisorComposeInputCursor, true);

	snprintf(g_OfficeVisorComposeInputHud, sizeof(g_OfficeVisorComposeInputHud),
			"> @%s: %s", g_OfficeVisorComposeInputAgentId, g_OfficeVisorComposeInputUser);

	if (strcmp(g_OfficeVisorComposeInputHud, g_OfficeVisorComposeInputLastHud) != 0) {
		strncpy(g_OfficeVisorComposeInputLastHud, g_OfficeVisorComposeInputHud,
				sizeof(g_OfficeVisorComposeInputLastHud) - 1);
		g_OfficeVisorComposeInputLastHud[sizeof(g_OfficeVisorComposeInputLastHud) - 1] = '\0';
		if (out_hud_line) {
			*out_hud_line = g_OfficeVisorComposeInputLastHud;
		}
	}

	if (result == 1) {
		snprintf(prefixed, sizeof(prefixed), "%s%s",
				OFFICE_VISOR_COMPOSE_PREFIX, g_OfficeVisorComposeInputUser);
		officeVisorComposeDoSubmit(g_OfficeVisorComposeInputAgentId, prefixed);
		snprintf(g_OfficeVisorComposeInputHud, sizeof(g_OfficeVisorComposeInputHud),
				"Sent to @%s", g_OfficeVisorComposeInputAgentId);
		if (out_hud_line) {
			*out_hud_line = g_OfficeVisorComposeInputHud;
		}
		officeServiceBridgeVisorComposeCancelInput();
		return 1;
	}

	if (result == -1) {
		officeServiceBridgeVisorComposeCancelInput();
		return -1;
	}

	return 0;
}

s32 officeServiceBridgeTryConsumeVisorComposeFeedback(const char **out_feedback)
{
	s32 ready = 0;

	if (out_feedback) {
		*out_feedback = NULL;
	}

	pthread_mutex_lock(&g_OfficeVisorComposeMutex);
	if (g_OfficeVisorComposeFeedbackReady && g_OfficeVisorComposeFeedback[0]) {
		if (out_feedback) {
			*out_feedback = g_OfficeVisorComposeFeedback;
		}
		g_OfficeVisorComposeFeedbackReady = 0;
		ready = 1;
	}
	pthread_mutex_unlock(&g_OfficeVisorComposeMutex);
	return ready;
}

const char *officeServiceBridgeConsoleSummaryText(u32 text_id, const char *lang_fallback)
{
	const char *live;

	if (!officeHubActive() || !officeConsoleTextMatchesStage(text_id)) {
		return lang_fallback;
	}

	officePollThreadEnsureStarted();
	live = officeServiceBridgeGetLiveSummary();
	if (live) {
		return live;
	}

	return lang_fallback;
}

const char *officeServiceBridgeAgentExamineText(u32 text_id, const char *lang_fallback)
{
	const char *agent_id;
	const char *cached = NULL;
	const u64 now = officeNowUs();

	if (!officeHubActive() || !g_OfficeServiceEnabled || !lang_fallback) {
		return lang_fallback;
	}

	agent_id = officeAgentIdForExamineText(text_id);
	if (!agent_id) {
		return lang_fallback;
	}

	officePollThreadEnsureStarted();

	/* Pass 35: Security Z-target shows pending connector approval card instead of walk-up DM. */
	if (officeSecurityConnectorIsSecurityText(text_id)) {
		pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
		if (g_OfficeSecurityConnectorHudLen > 0 && g_OfficeSecurityConnectorHud[0]) {
			cached = g_OfficeSecurityConnectorHud;
		}
		pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
		if (cached) {
			return cached;
		}
	}

	/* Pass 37: Comms Z-target shows connector stage HUD instead of walk-up DM. */
	if (officeCommsConnectorIsCommsText(text_id)) {
		pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
		if (g_OfficeCommsConnectorStageHudLen > 0 && g_OfficeCommsConnectorStageHud[0]) {
			cached = g_OfficeCommsConnectorStageHud;
		}
		pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
		if (cached) {
			return cached;
		}
	}

	pthread_mutex_lock(&g_OfficeWalkUpMutex);
	if (g_OfficeLastDmTextId == text_id && g_OfficeDmHudTextLen > 0 && g_OfficeDmHudText[0]
			&& g_OfficeLastDmAttemptUs != 0
			&& now - g_OfficeLastDmAttemptUs < OFFICE_DM_COOLDOWN_US) {
		cached = g_OfficeDmHudText;
	}
	if (!cached && g_OfficeLastDmTextId == text_id && g_OfficeDmHudTextLen > 0 && g_OfficeDmHudText[0]) {
		cached = g_OfficeDmHudText;
	}
	pthread_mutex_unlock(&g_OfficeWalkUpMutex);

	if (cached) {
		return cached;
	}

	/* Pass 13: enqueue worker POST; main thread never blocks on HTTP. */
	officeWalkUpEnqueue(text_id, agent_id);
	return lang_fallback;
}

s32 officeServiceBridgeSecurityConnectorPending(void)
{
	s32 pending;

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	pending = (g_OfficeSecurityConnectorApprovalIdLen > 0
			&& g_OfficeSecurityConnectorApprovalId[0]
			&& g_OfficeSecurityConnectorHudLen > 0
			&& g_OfficeSecurityConnectorHud[0]) ? 1 : 0;
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
	return pending;
}

void officeServiceBridgeTrackSecurityConnectorWait(s16 chrnum, u32 text_id)
{
	if (!officeSecurityConnectorIsSecurityText(text_id)) {
		return;
	}

	g_OfficeSecurityConnectorWaitChrnum = chrnum;
	g_OfficeSecurityConnectorWaitTextId = text_id;
}

void officeServiceBridgeClearSecurityConnectorWait(void)
{
	g_OfficeSecurityConnectorWaitChrnum = -1;
	g_OfficeSecurityConnectorWaitTextId = 0;
}

void officeServiceBridgeSecurityConnectorSubmit(s32 approve)
{
	char approval_id[OFFICE_SECURITY_CONNECTOR_ID_CAP];

	if (!officeHubActive() || !g_OfficeServiceEnabled) {
		return;
	}

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	if (g_OfficeSecurityConnectorApprovalIdLen <= 0 || !g_OfficeSecurityConnectorApprovalId[0]) {
		pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
		return;
	}
	strncpy(approval_id, g_OfficeSecurityConnectorApprovalId, sizeof(approval_id) - 1);
	approval_id[sizeof(approval_id) - 1] = '\0';
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);

	officePollThreadEnsureStarted();
	officeSecurityConnectorEnqueue(approval_id, approve);
}

void officeServiceBridgeSecurityConnectorCycle(s32 direction)
{
	s32 count;

	if (!officeHubActive() || !g_OfficeServiceEnabled) {
		return;
	}

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	count = g_OfficeSecurityConnectorPickerCount;
	if (count <= 1) {
		pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
		return;
	}

	if (direction > 0) {
		g_OfficeSecurityConnectorPickerIndex =
				(g_OfficeSecurityConnectorPickerIndex + 1) % count;
	} else if (direction < 0) {
		g_OfficeSecurityConnectorPickerIndex =
				(g_OfficeSecurityConnectorPickerIndex + count - 1) % count;
	}
	officeSecurityConnectorSyncSelected();
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
}

const char *officeServiceBridgeSecurityConnectorSelectedHud(void)
{
	const char *hud = NULL;

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	if (g_OfficeSecurityConnectorHudLen > 0 && g_OfficeSecurityConnectorHud[0]) {
		hud = g_OfficeSecurityConnectorHud;
	}
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
	return hud;
}

s32 officeServiceBridgeTryConsumeSecurityConnectorFeedback(const char **out_feedback)
{
	s32 ready;

	if (!out_feedback) {
		return 0;
	}

	*out_feedback = NULL;

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	ready = g_OfficeSecurityConnectorFeedbackReady;
	if (ready) {
		*out_feedback = g_OfficeSecurityConnectorFeedback;
		g_OfficeSecurityConnectorFeedbackReady = 0;
	}
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
	return ready;
}

s32 officeServiceBridgeSecurityConnectorBusy(void)
{
	s32 busy;

	pthread_mutex_lock(&g_OfficeSecurityConnectorMutex);
	busy = g_OfficeSecurityConnectorBusy;
	pthread_mutex_unlock(&g_OfficeSecurityConnectorMutex);
	return busy;
}

s32 officeServiceBridgeCommsConnectorStageReady(void)
{
	s32 ready;

	pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
	ready = (g_OfficeCommsConnectorStageHudLen > 0 && g_OfficeCommsConnectorStageHud[0]
			&& g_OfficeCommsConnectorStageIntentLen > 0 && g_OfficeCommsConnectorStageIntent[0]
			&& g_OfficeCommsConnectorStageChannelLen > 0 && g_OfficeCommsConnectorStageChannel[0]
			&& g_OfficeCommsConnectorStageTextLen > 0 && g_OfficeCommsConnectorStageText[0]) ? 1 : 0;
	pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
	return ready;
}

void officeServiceBridgeTrackCommsConnectorWait(s16 chrnum, u32 text_id)
{
	if (!officeCommsConnectorIsCommsText(text_id)) {
		return;
	}

	g_OfficeCommsConnectorWaitChrnum = chrnum;
	g_OfficeCommsConnectorWaitTextId = text_id;
}

void officeServiceBridgeClearCommsConnectorWait(void)
{
	g_OfficeCommsConnectorWaitChrnum = -1;
	g_OfficeCommsConnectorWaitTextId = 0;
}

void officeServiceBridgeCommsConnectorStageSubmit(void)
{
	char intent[OFFICE_COMMS_CONNECTOR_INTENT_CAP];
	char channel[OFFICE_COMMS_CONNECTOR_CHANNEL_CAP];
	char text[OFFICE_COMMS_CONNECTOR_TEXT_CAP];
	const u64 now = officeNowUs();

	if (!officeHubActive() || !g_OfficeServiceEnabled) {
		return;
	}

	if (g_OfficeLastCommsConnectorStageUs != 0
			&& now - g_OfficeLastCommsConnectorStageUs < OFFICE_COMMS_CONNECTOR_STAGE_COOLDOWN_US) {
		return;
	}

	pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
	if (g_OfficeCommsConnectorStageIntentLen <= 0 || !g_OfficeCommsConnectorStageIntent[0]
			|| g_OfficeCommsConnectorStageChannelLen <= 0 || !g_OfficeCommsConnectorStageChannel[0]
			|| g_OfficeCommsConnectorStageTextLen <= 0 || !g_OfficeCommsConnectorStageText[0]) {
		pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
		return;
	}
	strncpy(intent, g_OfficeCommsConnectorStageIntent, sizeof(intent) - 1);
	intent[sizeof(intent) - 1] = '\0';
	strncpy(channel, g_OfficeCommsConnectorStageChannel, sizeof(channel) - 1);
	channel[sizeof(channel) - 1] = '\0';
	strncpy(text, g_OfficeCommsConnectorStageText, sizeof(text) - 1);
	text[sizeof(text) - 1] = '\0';
	pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);

	officePollThreadEnsureStarted();
	g_OfficeLastCommsConnectorStageUs = now;
	officeCommsConnectorEnqueue(intent, channel, text);
}

s32 officeServiceBridgeTryConsumeCommsConnectorFeedback(const char **out_feedback)
{
	s32 ready;

	if (!out_feedback) {
		return 0;
	}

	*out_feedback = NULL;

	pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
	ready = g_OfficeCommsConnectorFeedbackReady;
	if (ready) {
		*out_feedback = g_OfficeCommsConnectorFeedback;
		g_OfficeCommsConnectorFeedbackReady = 0;
	}
	pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
	return ready;
}

s32 officeServiceBridgeCommsConnectorBusy(void)
{
	s32 busy;

	pthread_mutex_lock(&g_OfficeCommsConnectorMutex);
	busy = g_OfficeCommsConnectorBusy;
	pthread_mutex_unlock(&g_OfficeCommsConnectorMutex);
	return busy;
}

PD_CONSTRUCTOR static void officeServiceConfigInit(void)
{
	const char *env;

	configRegisterInt("OfficeService.Enabled", &g_OfficeServiceEnabled, 0, 1);
	configRegisterInt("OfficeService.Port", &g_OfficeServicePort, 1024, 65535);

	env = getenv("BOOT_OPEN_CONSOLE");
	if ((env && env[0] && env[0] != '0') || sysArgCheck("--boot-open-console")) {
		g_OfficeBootOpenConsole = 1;
		sysLogPrintf(LOG_NOTE, "[office-bridge] BOOT_OPEN_CONSOLE armed");
	}
}

#else /* PLATFORM_N64 or non-POSIX */

void officeServiceBridgeInit(void) {}
void officeServiceBridgeShutdown(void) {}
void officeServiceBridgeTick(void) {}
void officeServiceBridgeRefreshIfStale(void) {}

const char *officeServiceBridgeGetLiveSummary(void)
{
	return NULL;
}

const char *officeServiceBridgePerfectMenuText(void)
{
	return NULL;
}

const char *officeServiceBridgeMonitorText(const char *agent_id)
{
	(void)agent_id;
	return NULL;
}

const char *officeServiceBridgeVisorNotificationText(void)
{
	return NULL;
}

const char *officeServiceBridgeVisorRailText(void)
{
	return NULL;
}

const char *officeServiceBridgeVisorScrollbackText(void)
{
	return NULL;
}

const char *officeServiceBridgeVisorComposeHintText(void)
{
	return NULL;
}

void officeServiceBridgeVisorComposeSubmit(void) {}

void officeServiceBridgeVisorComposeBeginInput(void) {}

void officeServiceBridgeVisorComposeCancelInput(void) {}

s32 officeServiceBridgeVisorComposeInputActive(void)
{
	return 0;
}

s32 officeServiceBridgeVisorComposeInputStep(const char **out_hud_line)
{
	if (out_hud_line) {
		*out_hud_line = NULL;
	}
	return 0;
}

s32 officeServiceBridgeTryConsumeVisorComposeFeedback(const char **out_feedback)
{
	if (out_feedback) {
		*out_feedback = NULL;
	}
	return 0;
}

const char *officeServiceBridgeConsoleSummaryText(u32 text_id, const char *lang_fallback)
{
	(void)text_id;
	return lang_fallback;
}

const char *officeServiceBridgeAgentExamineText(u32 text_id, const char *lang_fallback)
{
	(void)text_id;
	return lang_fallback;
}

void officeServiceBridgeTrackDmHudWait(s16 chrnum, u32 text_id)
{
	(void)chrnum;
	(void)text_id;
}

void officeServiceBridgeClearDmHudWait(void) {}

s32 officeServiceBridgeTryConsumeDmHudRefresh(s16 chrnum, const char **out_tail)
{
	(void)chrnum;
	if (out_tail) {
		*out_tail = NULL;
	}
	return 0;
}

s32 officeServiceBridgeSecurityConnectorPending(void)
{
	return 0;
}

void officeServiceBridgeTrackSecurityConnectorWait(s16 chrnum, u32 text_id)
{
	(void)chrnum;
	(void)text_id;
}

void officeServiceBridgeClearSecurityConnectorWait(void) {}

void officeServiceBridgeSecurityConnectorSubmit(s32 approve)
{
	(void)approve;
}

void officeServiceBridgeSecurityConnectorCycle(s32 direction)
{
	(void)direction;
}

const char *officeServiceBridgeSecurityConnectorSelectedHud(void)
{
	return NULL;
}

s32 officeServiceBridgeTryConsumeSecurityConnectorFeedback(const char **out_feedback)
{
	if (out_feedback) {
		*out_feedback = NULL;
	}
	return 0;
}

s32 officeServiceBridgeSecurityConnectorBusy(void)
{
	return 0;
}

void officeCommsConnectorTick(void) {}

s32 officeServiceBridgeCommsConnectorStageReady(void)
{
	return 0;
}

void officeServiceBridgeTrackCommsConnectorWait(s16 chrnum, u32 text_id)
{
	(void)chrnum;
	(void)text_id;
}

void officeServiceBridgeClearCommsConnectorWait(void) {}

void officeServiceBridgeCommsConnectorStageSubmit(void) {}

s32 officeServiceBridgeTryConsumeCommsConnectorFeedback(const char **out_feedback)
{
	if (out_feedback) {
		*out_feedback = NULL;
	}
	return 0;
}

s32 officeServiceBridgeCommsConnectorBusy(void)
{
	return 0;
}

#endif
