#define _XOPEN_SOURCE 600

#include <assert.h>
#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdnoreturn.h>
#include <string.h>
#include <tgmath.h>
#include <time.h>

#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <unistd.h>
#include <poll.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/uio.h>
#include <sys/un.h>

#define len(a) (sizeof(a) / sizeof(*(a)))

#define assert_compatible_ptrs(a, b) ((void)sizeof((a) == (b)))

#define ptr_pair_elem_size(a, b) ( \
	assert_compatible_ptrs(a, b), \
	sizeof(*_Generic((b), \
		void *: (a), \
		default: (b))))

#define copy(dst, src, n) ((void)memcpy((dst), (src), (n) * ptr_pair_elem_size((dst), (src))))
#define move(dst, src, n) ((void)memmove((dst), (src), (n) * ptr_pair_elem_size((dst), (src))))
#define fillbytes(dst, b, n) ((void)memset((dst), (b), (n) * sizeof(*(dst))))
#define samebytes(dst, src, n) (memcmp((dst), (src), (n) * ptr_pair_elem_size((dst), (src))) == 0)

#ifdef __GNUC__
#	define NOINLINE __attribute__((__noinline__))
#	define UNUSED __attribute__((__unused__))
#	ifndef unreachable
#		define unreachable() __builtin_unreachable()
#	endif
#else
#	define NOINLINE
#	define UNUSED
#	ifndef unreachable
#		define unreachable()
#	endif
#endif

typedef unsigned int uint;

typedef ptrdiff_t isize; // technically not necessarily the same as ssize_t, oh well.
typedef size_t usize;

typedef signed char i8;
typedef int16_t i16;
typedef int32_t i32;
typedef int64_t i64;

typedef unsigned char u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;

typedef float f32;
typedef double f64;

static inline noreturn void die(char *fmt, ...) {
	va_list va;
	va_start(va, fmt);
	vfprintf(stderr, fmt, va);
	va_end(va);
	fputc('\n', stderr);
	exit(1);
}

static inline noreturn void dieerror(char *prefix) {
	perror(prefix);
	exit(1);
}

static inline i64 gettime(void) {
	struct timespec now_ts;
	if (clock_gettime(CLOCK_MONOTONIC, &now_ts) < 0)
		dieerror("clock_gettime");
	return (i64)now_ts.tv_sec * 1000000000 + now_ts.tv_nsec;
}

static UNUSED NOINLINE void hexdump(FILE *f, void *start, void *limit) {
	for (u8 *ptr = start; ptr < (u8 *)limit; ++ptr)
		fprintf(f, ptr == start ? "%02x" : " %02x", *ptr);
}

static UNUSED NOINLINE void pretty_hexdump(FILE *f, char *prefix, void *start, void *limit) {
	for (u8 *ptr = start;; ptr += 16) {
		usize rem = (u8 *)limit - ptr;
		fputs(prefix, f);
		fprintf(f, "%08zx   ", ptr - (u8 *)start);
		for (usize i = 0; i < 16; ++i) {
			if (i == 8)
				fputc(' ', f);
			if (i < rem)
				fprintf(f, "%02x ", ptr[i]);
			else
				fputs("   ", f);
		}
		fputc(' ', f);
		fputc(' ', f);
		for (usize i = 0; i < 16; ++i) {
			if (i == 8)
				fputc(' ', f);
			fputc(i >= rem ? ' ' : isprint(ptr[i]) && !isspace(ptr[i]) ? ptr[i] : '.', f);
		}
		fputc('\n', f);
		if (rem <= 16)
			break;
	}
}

struct dec {
	u8 *ptr;
	u8 *limit;
	u8 *errpos;
	char *error;
};

static inline void dec_error(struct dec *d, u8 *pos, char *msg) {
	if (d->error)
		return; // ahem
	d->errpos = pos;
	d->error = msg;
}

static inline bool dec_end(struct dec *d) {
	if (d->ptr != d->limit) {
		dec_error(d, d->ptr, "expected end of input");
		return false;
	}
	return true;
}

static inline bool dec_advance(struct dec *d, usize n) {
	if ((usize)(d->limit - d->ptr) < n) {
		dec_error(d, d->limit, "unexpected end of input");
		return false;
	}
	d->ptr += n;
	return true;
}

static inline bool dec_u8(struct dec *d, u8 *v) {
	u8 *ptr = d->ptr;
	if (!dec_advance(d, 1))
		return false;
	*v = *ptr;
	return true;
}

static inline bool dec_u16(struct dec *d, u16 *v) {
	u8 *ptr = d->ptr;
	if (!dec_advance(d, 2))
		return false;
	*v = (u16)ptr[0] << 8 | ptr[1];
	return true;
}

static inline bool dec_u32(struct dec *d, u32 *v) {
	u8 *ptr = d->ptr;
	if (!dec_advance(d, 4))
		return false;
	*v = (u32)ptr[0] << 24 | (u64)ptr[1] << 16
		| (u32)ptr[2] << 8 | (u32)ptr[3];
	return true;
}

static inline bool dec_u64(struct dec *d, u64 *v) {
	u8 *ptr = d->ptr;
	if (!dec_advance(d, 8))
		return false;
	*v = (u64)ptr[0] << 56 | (u64)ptr[1] << 48
		| (u64)ptr[2] << 40 | (u64)ptr[3] << 32
		| (u64)ptr[4] << 24 | (u64)ptr[5] << 16
		| (u64)ptr[6] << 8 | (u64)ptr[7];
	return true;
}

static inline bool dec_i8(struct dec *d, i8 *v) {
	return dec_u8(d, (u8 *)v);
}

static inline bool dec_i16(struct dec *d, i16 *v) {
	return dec_u16(d, (u16 *)v);
}

static inline bool dec_i32(struct dec *d, i32 *v) {
	return dec_u32(d, (u32 *)v);
}

static inline bool dec_i64(struct dec *d, i64 *v) {
	return dec_u64(d, (u64 *)v);
}

static inline bool dec_bool(struct dec *d, bool *v) {
	u8 u;
	if (!dec_u8(d, &u))
		return false;
	*v = u;
	return true;
}

static inline bool dec_f32(struct dec *d, f32 *v) {
	static_assert(sizeof(u32) == sizeof(f32));
	u32 u;
	if (!dec_u32(d, &u))
		return false;
	memcpy(v, &u, sizeof(u));
	return true;
}

static inline bool dec_f64(struct dec *d, f64 *v) {
	static_assert(sizeof(u64) == sizeof(f64));
	u64 u;
	if (!dec_u64(d, &u))
		return false;
	memcpy(v, &u, sizeof(u));
	return true;
}

static inline bool dec_v32(struct dec *d, i32 *v) {
	u8 *ptr = d->ptr;
	*v = 0;
	for (int i = 0;; i += 7) {
		u8 b;
		if (!dec_u8(d, &b))
			return false;
		if (b & ~(UINT32_MAX >> i)) {
			dec_error(d, ptr, "var32 too big");
			return false;
		}
		*v |= (u32)(b & 0x7f) << i;
		if (!(b & 0x80))
			return true;
	}
}

static inline bool dec_v64(struct dec *d, i64 *v) {
	u8 *ptr = d->ptr;
	*v = 0;
	for (int i = 0;; i += 7) {
		u8 b;
		if (!dec_u8(d, &b))
			return false;
		if (b & ~(UINT64_MAX >> i)) {
			dec_error(d, ptr, "var64 too big");
			return false;
		}
		*v |= (u64)(b & 0x7f) << i;
		if (!(b & 0x80))
			return true;
	}
}

static inline bool dec_pos(struct dec *d, i32 *x, i32 *y, i32 *z) {
	u64 v;
	if (!dec_u64(d, &v))
		return false;
	*x = (i32)(v >> 32) >> 6;
	*y = (i32)(v << 20) >> 20;
	*z = (i32)(v >> 6) >> 6;
	return true;
}

static inline bool dec_str(struct dec *d, char **s, i32 *len, i32 maxlen) {
	u8 *ptr = d->ptr;
	if (!dec_v32(d, len))
		return false;
	if (*len < 0) {
		dec_error(d, ptr, "string too short");
		return false;
	}
	if (*len > maxlen) {
		dec_error(d, ptr, "string too long");
		return false;
	}
	*s = (char *)d->ptr;
	if (!dec_advance(d, *len))
		return false;
	// validate utf-8
	return true;
}

static inline bool dec_strncpy(struct dec *d, char *s, i32 maxlen) {
	char *src;

	i32 len;
	if (!dec_str(d, &src, &len, maxlen - 1))
		return false;
	copy(s, src, len);
	s[len] = '\0';
	return true;
}

struct enc {
	u8 *ptr;
	u8 *limit;
	bool trunc;
};

static inline u8 *enc_advance(struct enc *e, usize n) {
	if ((usize)(e->limit - e->ptr) < n) {
		e->trunc = true;
		return NULL;
	}
	u8 *ptr = e->ptr;
	// XXX: there's a really annoying optimization problem with the use of
	// NULL to mean "truncated" here. the compiler will exclaim: "bUt wHaT
	// If eNc->PTr iS NUlL??", and end up generating two branches. i still
	// like this API over a separate bool return, so...
	if (!ptr)
		unreachable();
	e->ptr += n;
	return ptr;
}

static inline void enc_copy(struct enc *e, void *data, usize n) {
	u8 *ptr = enc_advance(e, n);
	if (!ptr)
		return;
	if (n != 0) // memcpy(ptr, NULL, 0); :(
		copy(ptr, data, n);
}

static inline void enc_u8(struct enc *e, u8 v) {
	u8 *ptr = enc_advance(e, 1);
	if (!ptr)
		return;
	*ptr = v;
}

static inline void enc_u16(struct enc *e, u16 v) {
	u8 *ptr = enc_advance(e, 2);
	if (!ptr)
		return;
	ptr[0] = (u8)(v >> 8);
	ptr[1] = (u8)v;
}

static inline void enc_u32(struct enc *e, u32 v) {
	u8 *ptr = enc_advance(e, 4);
	if (!ptr)
		return;
	ptr[0] = (u8)(v >> 24);
	ptr[1] = (u8)(v >> 16);
	ptr[2] = (u8)(v >> 8);
	ptr[3] = (u8)v;
}

static inline void enc_u64(struct enc *e, u64 v) {
	u8 *ptr = enc_advance(e, 8);
	if (!ptr)
		return;
	ptr[0] = (u8)(v >> 56);
	ptr[1] = (u8)(v >> 48);
	ptr[2] = (u8)(v >> 40);
	ptr[3] = (u8)(v >> 32);
	ptr[4] = (u8)(v >> 24);
	ptr[5] = (u8)(v >> 16);
	ptr[6] = (u8)(v >> 8);
	ptr[7] = (u8)v;
}

static inline void enc_i8(struct enc *e, i8 v) {
	enc_u8(e, v);
}

static inline void enc_i16(struct enc *e, i16 v) {
	enc_u16(e, v);
}

static inline void enc_i32(struct enc *e, i32 v) {
	enc_u32(e, v);
}

static inline void enc_i64(struct enc *e, i64 v) {
	enc_u64(e, v);
}

static inline void enc_bool(struct enc *e, bool v) {
	enc_u8(e, v);
}

static inline void enc_f32(struct enc *e, f32 v) {
	static_assert(sizeof(u32) == sizeof(f32));
	u32 u;
	memcpy(&u, &v, sizeof(u));
	enc_u32(e, u);
}

static inline void enc_f64(struct enc *e, f64 v) {
	static_assert(sizeof(u64) == sizeof(f64));
	u64 u;
	memcpy(&u, &v, sizeof(u));
	enc_u64(e, u);
}

static inline void enc_v32(struct enc *e, i32 v) {
	u32 u = v;
	do {
		u8 b = u & 0x7f;
		u >>= 7;
		if (u)
			b |= 0x80;
		enc_u8(e, b);
	} while (u);
}

static inline void enc_v64(struct enc *e, i64 v) {
	u64 u = v;
	do {
		u8 b = u & 0x7f;
		u >>= 7;
		if (u)
			b |= 0x80;
		enc_u8(e, b);
	} while (u);
}

static inline void enc_pos(struct enc *e, i32 x, i32 y, i32 z) {
	enc_u64(e, ((u64)x & 0x3ffffff) << 38 |
		((u64)y & 0xfff) |
		((u64)z & 0x3ffffff) << 12);
}

static inline void enc_str(struct enc *e, char *str) {
	usize len = strlen(str);
	enc_v32(e, len);
	enc_copy(e, str, len);
}

enum {
	HANDSHAKE_S_INTENTION = 0,
	HANDSHAKE_S_NPACKETS,
};

enum {
	STATUS_C_STATUS_RESPONSE = 0,
	STATUS_C_PONG_RESPONSE = 1,
	STATUS_C_NPACKETS,
};

enum {
	STATUS_S_STATUS_REQUEST = 0,
	STATUS_S_PING_REQUEST = 1,
	STATUS_S_NPACKETS,
};

enum {
	LOGIN_C_LOGIN_DISCONNECT = 0,
	LOGIN_C_HELLO = 1,
	LOGIN_C_LOGIN_FINISHED = 2,
	LOGIN_C_LOGIN_COMPRESSION = 3,
	LOGIN_C_CUSTOM_QUERY = 4,
	LOGIN_C_COOKIE_REQUEST = 5,
	LOGIN_C_NPACKETS,
};

enum {
	LOGIN_S_HELLO = 0,
	LOGIN_S_KEY = 1,
	LOGIN_S_CUSTOM_QUERY_ANSWER = 2,
	LOGIN_S_LOGIN_ACKNOWLEDGED = 3,
	LOGIN_S_COOKIE_RESPONSE = 4,
	LOGIN_S_NPACKETS,
};

enum {
	CONFIG_C_COOKIE_REQUEST = 0,
	CONFIG_C_CUSTOM_PAYLOAD = 1,
	CONFIG_C_DISCONNECT = 2,
	CONFIG_C_FINISH_CONFIGURATION = 3,
	CONFIG_C_KEEP_ALIVE = 4,
	CONFIG_C_PING = 5,
	CONFIG_C_RESET_CHAT = 6,
	CONFIG_C_REGISTRY_DATA = 7,
	CONFIG_C_RESOURCE_PACK_POP = 8,
	CONFIG_C_RESOURCE_PACK_PUSH = 9,
	CONFIG_C_STORE_COOKIE = 10,
	CONFIG_C_TRANSFER = 11,
	CONFIG_C_UPDATE_ENABLED_FEATURES = 12,
	CONFIG_C_UPDATE_TAGS = 13,
	CONFIG_C_SELECT_KNOWN_PACKS = 14,
	CONFIG_C_CUSTOM_REPORT_DETAILS = 15,
	CONFIG_C_SERVER_LINKS = 16,
	CONFIG_C_NPACKETS,
};

enum {
	CONFIG_S_CLIENT_INFORMATION = 0,
	CONFIG_S_COOKIE_RESPONSE = 1,
	CONFIG_S_CUSTOM_PAYLOAD = 2,
	CONFIG_S_FINISH_CONFIGURATION = 3,
	CONFIG_S_KEEP_ALIVE = 4,
	CONFIG_S_PONG = 5,
	CONFIG_S_RESOURCE_PACK = 6,
	CONFIG_S_SELECT_KNOWN_PACKS = 7,
	CONFIG_S_NPACKETS,
};

enum {
	PLAY_C_BUNDLE_DELIMITER = 0,
	PLAY_C_ADD_ENTITY = 1,
	PLAY_C_ANIMATE = 2,
	PLAY_C_AWARD_STATS = 3,
	PLAY_C_BLOCK_CHANGED_ACK = 4,
	PLAY_C_BLOCK_DESTRUCTION = 5,
	PLAY_C_BLOCK_ENTITY_DATA = 6,
	PLAY_C_BLOCK_EVENT = 7,
	PLAY_C_BLOCK_UPDATE = 8,
	PLAY_C_BOSS_EVENT = 9,
	PLAY_C_CHANGE_DIFFICULTY = 10,
	PLAY_C_CHUNK_BATCH_FINISHED = 11,
	PLAY_C_CHUNK_BATCH_START = 12,
	PLAY_C_CHUNKS_BIOMES = 13,
	PLAY_C_CLEAR_TITLES = 14,
	PLAY_C_COMMAND_SUGGESTIONS = 15,
	PLAY_C_COMMANDS = 16,
	PLAY_C_CONTAINER_CLOSE = 17,
	PLAY_C_CONTAINER_SET_CONTENT = 18,
	PLAY_C_CONTAINER_SET_DATA = 19,
	PLAY_C_CONTAINER_SET_SLOT = 20,
	PLAY_C_COOKIE_REQUEST = 21,
	PLAY_C_COOLDOWN = 22,
	PLAY_C_CUSTOM_CHAT_COMPLETIONS = 23,
	PLAY_C_CUSTOM_PAYLOAD = 24,
	PLAY_C_DAMAGE_EVENT = 25,
	PLAY_C_DEBUG_SAMPLE = 26,
	PLAY_C_DELETE_CHAT = 27,
	PLAY_C_DISCONNECT = 28,
	PLAY_C_DISGUISED_CHAT = 29,
	PLAY_C_ENTITY_EVENT = 30,
	PLAY_C_ENTITY_POSITION_SYNC = 31,
	PLAY_C_EXPLODE = 32,
	PLAY_C_FORGET_LEVEL_CHUNK = 33,
	PLAY_C_GAME_EVENT = 34,
	PLAY_C_HORSE_SCREEN_OPEN = 35,
	PLAY_C_HURT_ANIMATION = 36,
	PLAY_C_INITIALIZE_BORDER = 37,
	PLAY_C_KEEP_ALIVE = 38,
	PLAY_C_LEVEL_CHUNK_WITH_LIGHT = 39,
	PLAY_C_LEVEL_EVENT = 40,
	PLAY_C_LEVEL_PARTICLES = 41,
	PLAY_C_LIGHT_UPDATE = 42,
	PLAY_C_LOGIN = 43,
	PLAY_C_MAP_ITEM_DATA = 44,
	PLAY_C_MERCHANT_OFFERS = 45,
	PLAY_C_MOVE_ENTITY_POS = 46,
	PLAY_C_MOVE_ENTITY_POS_ROT = 47,
	PLAY_C_MOVE_MINECART_ALONG_TRACK = 48,
	PLAY_C_MOVE_ENTITY_ROT = 49,
	PLAY_C_MOVE_VEHICLE = 50,
	PLAY_C_OPEN_BOOK = 51,
	PLAY_C_OPEN_SCREEN = 52,
	PLAY_C_OPEN_SIGN_EDITOR = 53,
	PLAY_C_PING = 54,
	PLAY_C_PONG_RESPONSE = 55,
	PLAY_C_PLACE_GHOST_RECIPE = 56,
	PLAY_C_PLAYER_ABILITIES = 57,
	PLAY_C_PLAYER_CHAT = 58,
	PLAY_C_PLAYER_COMBAT_END = 59,
	PLAY_C_PLAYER_COMBAT_ENTER = 60,
	PLAY_C_PLAYER_COMBAT_KILL = 61,
	PLAY_C_PLAYER_INFO_REMOVE = 62,
	PLAY_C_PLAYER_INFO_UPDATE = 63,
	PLAY_C_PLAYER_LOOK_AT = 64,
	PLAY_C_PLAYER_POSITION = 65,
	PLAY_C_PLAYER_ROTATION = 66,
	PLAY_C_RECIPE_BOOK_ADD = 67,
	PLAY_C_RECIPE_BOOK_REMOVE = 68,
	PLAY_C_RECIPE_BOOK_SETTINGS = 69,
	PLAY_C_REMOVE_ENTITIES = 70,
	PLAY_C_REMOVE_MOB_EFFECT = 71,
	PLAY_C_RESET_SCORE = 72,
	PLAY_C_RESOURCE_PACK_POP = 73,
	PLAY_C_RESOURCE_PACK_PUSH = 74,
	PLAY_C_RESPAWN = 75,
	PLAY_C_ROTATE_HEAD = 76,
	PLAY_C_SECTION_BLOCKS_UPDATE = 77,
	PLAY_C_SELECT_ADVANCEMENTS_TAB = 78,
	PLAY_C_SERVER_DATA = 79,
	PLAY_C_SET_ACTION_BAR_TEXT = 80,
	PLAY_C_SET_BORDER_CENTER = 81,
	PLAY_C_SET_BORDER_LERP_SIZE = 82,
	PLAY_C_SET_BORDER_SIZE = 83,
	PLAY_C_SET_BORDER_WARNING_DELAY = 84,
	PLAY_C_SET_BORDER_WARNING_DISTANCE = 85,
	PLAY_C_SET_CAMERA = 86,
	PLAY_C_SET_CHUNK_CACHE_CENTER = 87,
	PLAY_C_SET_CHUNK_CACHE_RADIUS = 88,
	PLAY_C_SET_CURSOR_ITEM = 89,
	PLAY_C_SET_DEFAULT_SPAWN_POSITION = 90,
	PLAY_C_SET_DISPLAY_OBJECTIVE = 91,
	PLAY_C_SET_ENTITY_DATA = 92,
	PLAY_C_SET_ENTITY_LINK = 93,
	PLAY_C_SET_ENTITY_MOTION = 94,
	PLAY_C_SET_EQUIPMENT = 95,
	PLAY_C_SET_EXPERIENCE = 96,
	PLAY_C_SET_HEALTH = 97,
	PLAY_C_SET_HELD_SLOT = 98,
	PLAY_C_SET_OBJECTIVE = 99,
	PLAY_C_SET_PASSENGERS = 100,
	PLAY_C_SET_PLAYER_INVENTORY = 101,
	PLAY_C_SET_PLAYER_TEAM = 102,
	PLAY_C_SET_SCORE = 103,
	PLAY_C_SET_SIMULATION_DISTANCE = 104,
	PLAY_C_SET_SUBTITLE_TEXT = 105,
	PLAY_C_SET_TIME = 106,
	PLAY_C_SET_TITLE_TEXT = 107,
	PLAY_C_SET_TITLES_ANIMATION = 108,
	PLAY_C_SOUND_ENTITY = 109,
	PLAY_C_SOUND = 110,
	PLAY_C_START_CONFIGURATION = 111,
	PLAY_C_STOP_SOUND = 112,
	PLAY_C_STORE_COOKIE = 113,
	PLAY_C_SYSTEM_CHAT = 114,
	PLAY_C_TAB_LIST = 115,
	PLAY_C_TAG_QUERY = 116,
	PLAY_C_TAKE_ITEM_ENTITY = 117,
	PLAY_C_TELEPORT_ENTITY = 118,
	PLAY_C_TEST_INSTANCE_BLOCK_STATUS = 119,
	PLAY_C_TICKING_STATE = 120,
	PLAY_C_TICKING_STEP = 121,
	PLAY_C_TRANSFER = 122,
	PLAY_C_UPDATE_ADVANCEMENTS = 123,
	PLAY_C_UPDATE_ATTRIBUTES = 124,
	PLAY_C_UPDATE_MOB_EFFECT = 125,
	PLAY_C_UPDATE_RECIPES = 126,
	PLAY_C_UPDATE_TAGS = 127,
	PLAY_C_PROJECTILE_POWER = 128,
	PLAY_C_CUSTOM_REPORT_DETAILS = 129,
	PLAY_C_SERVER_LINKS = 130,
	PLAY_C_NPACKETS,
};

enum {
	PLAY_S_ACCEPT_TELEPORTATION = 0,
	PLAY_S_BLOCK_ENTITY_TAG_QUERY = 1,
	PLAY_S_BUNDLE_ITEM_SELECTED = 2,
	PLAY_S_CHANGE_DIFFICULTY = 3,
	PLAY_S_CHAT_ACK = 4,
	PLAY_S_CHAT_COMMAND = 5,
	PLAY_S_CHAT_COMMAND_SIGNED = 6,
	PLAY_S_CHAT = 7,
	PLAY_S_CHAT_SESSION_UPDATE = 8,
	PLAY_S_CHUNK_BATCH_RECEIVED = 9,
	PLAY_S_CLIENT_COMMAND = 10,
	PLAY_S_CLIENT_TICK_END = 11,
	PLAY_S_CLIENT_INFORMATION = 12,
	PLAY_S_COMMAND_SUGGESTION = 13,
	PLAY_S_CONFIGURATION_ACKNOWLEDGED = 14,
	PLAY_S_CONTAINER_BUTTON_CLICK = 15,
	PLAY_S_CONTAINER_CLICK = 16,
	PLAY_S_CONTAINER_CLOSE = 17,
	PLAY_S_CONTAINER_SLOT_STATE_CHANGED = 18,
	PLAY_S_COOKIE_RESPONSE = 19,
	PLAY_S_CUSTOM_PAYLOAD = 20,
	PLAY_S_DEBUG_SAMPLE_SUBSCRIPTION = 21,
	PLAY_S_EDIT_BOOK = 22,
	PLAY_S_ENTITY_TAG_QUERY = 23,
	PLAY_S_INTERACT = 24,
	PLAY_S_JIGSAW_GENERATE = 25,
	PLAY_S_KEEP_ALIVE = 26,
	PLAY_S_LOCK_DIFFICULTY = 27,
	PLAY_S_MOVE_PLAYER_POS = 28,
	PLAY_S_MOVE_PLAYER_POS_ROT = 29,
	PLAY_S_MOVE_PLAYER_ROT = 30,
	PLAY_S_MOVE_PLAYER_STATUS_ONLY = 31,
	PLAY_S_MOVE_VEHICLE = 32,
	PLAY_S_PADDLE_BOAT = 33,
	PLAY_S_PICK_ITEM_FROM_BLOCK = 34,
	PLAY_S_PICK_ITEM_FROM_ENTITY = 35,
	PLAY_S_PING_REQUEST = 36,
	PLAY_S_PLACE_RECIPE = 37,
	PLAY_S_PLAYER_ABILITIES = 38,
	PLAY_S_PLAYER_ACTION = 39,
	PLAY_S_PLAYER_COMMAND = 40,
	PLAY_S_PLAYER_INPUT = 41,
	PLAY_S_PLAYER_LOADED = 42,
	PLAY_S_PONG = 43,
	PLAY_S_RECIPE_BOOK_CHANGE_SETTINGS = 44,
	PLAY_S_RECIPE_BOOK_SEEN_RECIPE = 45,
	PLAY_S_RENAME_ITEM = 46,
	PLAY_S_RESOURCE_PACK = 47,
	PLAY_S_SEEN_ADVANCEMENTS = 48,
	PLAY_S_SELECT_TRADE = 49,
	PLAY_S_SET_BEACON = 50,
	PLAY_S_SET_CARRIED_ITEM = 51,
	PLAY_S_SET_COMMAND_BLOCK = 52,
	PLAY_S_SET_COMMAND_MINECART = 53,
	PLAY_S_SET_CREATIVE_MODE_SLOT = 54,
	PLAY_S_SET_JIGSAW_BLOCK = 55,
	PLAY_S_SET_STRUCTURE_BLOCK = 56,
	PLAY_S_SET_TEST_BLOCK = 57,
	PLAY_S_SIGN_UPDATE = 58,
	PLAY_S_SWING = 59,
	PLAY_S_TELEPORT_TO_ENTITY = 60,
	PLAY_S_TEST_INSTANCE_BLOCK_ACTION = 61,
	PLAY_S_USE_ITEM_ON = 62,
	PLAY_S_USE_ITEM = 63,
	PLAY_S_NPACKETS,
};

struct protocol_info {
	char *name;
	i32 nclientbound, nserverbound;
	char **clientbound_names, **serverbound_names;
};

static char *handshake_s_packet_names[HANDSHAKE_S_NPACKETS] = {
	[HANDSHAKE_S_INTENTION] = "minecraft:intention",
};

static char *status_c_packet_names[STATUS_C_NPACKETS] = {
	[STATUS_C_STATUS_RESPONSE] = "minecraft:status_response",
	[STATUS_C_PONG_RESPONSE] = "minecraft:pong_response",
};

static char *status_s_packet_names[STATUS_S_NPACKETS] = {
	[STATUS_S_STATUS_REQUEST] = "minecraft:status_request",
	[STATUS_S_PING_REQUEST] = "minecraft:ping_request",
};

static char *login_c_packet_names[LOGIN_C_NPACKETS] = {
	[LOGIN_C_LOGIN_DISCONNECT] = "minecraft:login_disconnect",
	[LOGIN_C_HELLO] = "minecraft:hello",
	[LOGIN_C_LOGIN_FINISHED] = "minecraft:login_finished",
	[LOGIN_C_LOGIN_COMPRESSION] = "minecraft:login_compression",
	[LOGIN_C_CUSTOM_QUERY] = "minecraft:custom_query",
	[LOGIN_C_COOKIE_REQUEST] = "minecraft:cookie_request",
};

static char *login_s_packet_names[LOGIN_S_NPACKETS] = {
	[LOGIN_S_HELLO] = "minecraft:hello",
	[LOGIN_S_KEY] = "minecraft:key",
	[LOGIN_S_CUSTOM_QUERY_ANSWER] = "minecraft:custom_query_answer",
	[LOGIN_S_LOGIN_ACKNOWLEDGED] = "minecraft:login_acknowledged",
	[LOGIN_S_COOKIE_RESPONSE] = "minecraft:cookie_response",
};

static char *config_c_packet_names[CONFIG_C_NPACKETS] = {
	[CONFIG_C_COOKIE_REQUEST] = "minecraft:cookie_request",
	[CONFIG_C_CUSTOM_PAYLOAD] = "minecraft:custom_payload",
	[CONFIG_C_DISCONNECT] = "minecraft:disconnect",
	[CONFIG_C_FINISH_CONFIGURATION] = "minecraft:finish_configuration",
	[CONFIG_C_KEEP_ALIVE] = "minecraft:keep_alive",
	[CONFIG_C_PING] = "minecraft:ping",
	[CONFIG_C_RESET_CHAT] = "minecraft:reset_chat",
	[CONFIG_C_REGISTRY_DATA] = "minecraft:registry_data",
	[CONFIG_C_RESOURCE_PACK_POP] = "minecraft:resource_pack_pop",
	[CONFIG_C_RESOURCE_PACK_PUSH] = "minecraft:resource_pack_push",
	[CONFIG_C_STORE_COOKIE] = "minecraft:store_cookie",
	[CONFIG_C_TRANSFER] = "minecraft:transfer",
	[CONFIG_C_UPDATE_ENABLED_FEATURES] = "minecraft:update_enabled_features",
	[CONFIG_C_UPDATE_TAGS] = "minecraft:update_tags",
	[CONFIG_C_SELECT_KNOWN_PACKS] = "minecraft:select_known_packs",
	[CONFIG_C_CUSTOM_REPORT_DETAILS] = "minecraft:custom_report_details",
	[CONFIG_C_SERVER_LINKS] = "minecraft:server_links",
};

static char *config_s_packet_names[CONFIG_S_NPACKETS] = {
	[CONFIG_S_CLIENT_INFORMATION] = "minecraft:client_information",
	[CONFIG_S_COOKIE_RESPONSE] = "minecraft:cookie_response",
	[CONFIG_S_CUSTOM_PAYLOAD] = "minecraft:custom_payload",
	[CONFIG_S_FINISH_CONFIGURATION] = "minecraft:finish_configuration",
	[CONFIG_S_KEEP_ALIVE] = "minecraft:keep_alive",
	[CONFIG_S_PONG] = "minecraft:pong",
	[CONFIG_S_RESOURCE_PACK] = "minecraft:resource_pack",
	[CONFIG_S_SELECT_KNOWN_PACKS] = "minecraft:select_known_packs",
};

static char *play_c_packet_names[PLAY_C_NPACKETS] = {
	[PLAY_C_BUNDLE_DELIMITER] = "minecraft:bundle_delimiter",
	[PLAY_C_ADD_ENTITY] = "minecraft:add_entity",
	[PLAY_C_ANIMATE] = "minecraft:animate",
	[PLAY_C_AWARD_STATS] = "minecraft:award_stats",
	[PLAY_C_BLOCK_CHANGED_ACK] = "minecraft:block_changed_ack",
	[PLAY_C_BLOCK_DESTRUCTION] = "minecraft:block_destruction",
	[PLAY_C_BLOCK_ENTITY_DATA] = "minecraft:block_entity_data",
	[PLAY_C_BLOCK_EVENT] = "minecraft:block_event",
	[PLAY_C_BLOCK_UPDATE] = "minecraft:block_update",
	[PLAY_C_BOSS_EVENT] = "minecraft:boss_event",
	[PLAY_C_CHANGE_DIFFICULTY] = "minecraft:change_difficulty",
	[PLAY_C_CHUNK_BATCH_FINISHED] = "minecraft:chunk_batch_finished",
	[PLAY_C_CHUNK_BATCH_START] = "minecraft:chunk_batch_start",
	[PLAY_C_CHUNKS_BIOMES] = "minecraft:chunks_biomes",
	[PLAY_C_CLEAR_TITLES] = "minecraft:clear_titles",
	[PLAY_C_COMMAND_SUGGESTIONS] = "minecraft:command_suggestions",
	[PLAY_C_COMMANDS] = "minecraft:commands",
	[PLAY_C_CONTAINER_CLOSE] = "minecraft:container_close",
	[PLAY_C_CONTAINER_SET_CONTENT] = "minecraft:container_set_content",
	[PLAY_C_CONTAINER_SET_DATA] = "minecraft:container_set_data",
	[PLAY_C_CONTAINER_SET_SLOT] = "minecraft:container_set_slot",
	[PLAY_C_COOKIE_REQUEST] = "minecraft:cookie_request",
	[PLAY_C_COOLDOWN] = "minecraft:cooldown",
	[PLAY_C_CUSTOM_CHAT_COMPLETIONS] = "minecraft:custom_chat_completions",
	[PLAY_C_CUSTOM_PAYLOAD] = "minecraft:custom_payload",
	[PLAY_C_DAMAGE_EVENT] = "minecraft:damage_event",
	[PLAY_C_DEBUG_SAMPLE] = "minecraft:debug_sample",
	[PLAY_C_DELETE_CHAT] = "minecraft:delete_chat",
	[PLAY_C_DISCONNECT] = "minecraft:disconnect",
	[PLAY_C_DISGUISED_CHAT] = "minecraft:disguised_chat",
	[PLAY_C_ENTITY_EVENT] = "minecraft:entity_event",
	[PLAY_C_ENTITY_POSITION_SYNC] = "minecraft:entity_position_sync",
	[PLAY_C_EXPLODE] = "minecraft:explode",
	[PLAY_C_FORGET_LEVEL_CHUNK] = "minecraft:forget_level_chunk",
	[PLAY_C_GAME_EVENT] = "minecraft:game_event",
	[PLAY_C_HORSE_SCREEN_OPEN] = "minecraft:horse_screen_open",
	[PLAY_C_HURT_ANIMATION] = "minecraft:hurt_animation",
	[PLAY_C_INITIALIZE_BORDER] = "minecraft:initialize_border",
	[PLAY_C_KEEP_ALIVE] = "minecraft:keep_alive",
	[PLAY_C_LEVEL_CHUNK_WITH_LIGHT] = "minecraft:level_chunk_with_light",
	[PLAY_C_LEVEL_EVENT] = "minecraft:level_event",
	[PLAY_C_LEVEL_PARTICLES] = "minecraft:level_particles",
	[PLAY_C_LIGHT_UPDATE] = "minecraft:light_update",
	[PLAY_C_LOGIN] = "minecraft:login",
	[PLAY_C_MAP_ITEM_DATA] = "minecraft:map_item_data",
	[PLAY_C_MERCHANT_OFFERS] = "minecraft:merchant_offers",
	[PLAY_C_MOVE_ENTITY_POS] = "minecraft:move_entity_pos",
	[PLAY_C_MOVE_ENTITY_POS_ROT] = "minecraft:move_entity_pos_rot",
	[PLAY_C_MOVE_MINECART_ALONG_TRACK] = "minecraft:move_minecart_along_track",
	[PLAY_C_MOVE_ENTITY_ROT] = "minecraft:move_entity_rot",
	[PLAY_C_MOVE_VEHICLE] = "minecraft:move_vehicle",
	[PLAY_C_OPEN_BOOK] = "minecraft:open_book",
	[PLAY_C_OPEN_SCREEN] = "minecraft:open_screen",
	[PLAY_C_OPEN_SIGN_EDITOR] = "minecraft:open_sign_editor",
	[PLAY_C_PING] = "minecraft:ping",
	[PLAY_C_PONG_RESPONSE] = "minecraft:pong_response",
	[PLAY_C_PLACE_GHOST_RECIPE] = "minecraft:place_ghost_recipe",
	[PLAY_C_PLAYER_ABILITIES] = "minecraft:player_abilities",
	[PLAY_C_PLAYER_CHAT] = "minecraft:player_chat",
	[PLAY_C_PLAYER_COMBAT_END] = "minecraft:player_combat_end",
	[PLAY_C_PLAYER_COMBAT_ENTER] = "minecraft:player_combat_enter",
	[PLAY_C_PLAYER_COMBAT_KILL] = "minecraft:player_combat_kill",
	[PLAY_C_PLAYER_INFO_REMOVE] = "minecraft:player_info_remove",
	[PLAY_C_PLAYER_INFO_UPDATE] = "minecraft:player_info_update",
	[PLAY_C_PLAYER_LOOK_AT] = "minecraft:player_look_at",
	[PLAY_C_PLAYER_POSITION] = "minecraft:player_position",
	[PLAY_C_PLAYER_ROTATION] = "minecraft:player_rotation",
	[PLAY_C_RECIPE_BOOK_ADD] = "minecraft:recipe_book_add",
	[PLAY_C_RECIPE_BOOK_REMOVE] = "minecraft:recipe_book_remove",
	[PLAY_C_RECIPE_BOOK_SETTINGS] = "minecraft:recipe_book_settings",
	[PLAY_C_REMOVE_ENTITIES] = "minecraft:remove_entities",
	[PLAY_C_REMOVE_MOB_EFFECT] = "minecraft:remove_mob_effect",
	[PLAY_C_RESET_SCORE] = "minecraft:reset_score",
	[PLAY_C_RESOURCE_PACK_POP] = "minecraft:resource_pack_pop",
	[PLAY_C_RESOURCE_PACK_PUSH] = "minecraft:resource_pack_push",
	[PLAY_C_RESPAWN] = "minecraft:respawn",
	[PLAY_C_ROTATE_HEAD] = "minecraft:rotate_head",
	[PLAY_C_SECTION_BLOCKS_UPDATE] = "minecraft:section_blocks_update",
	[PLAY_C_SELECT_ADVANCEMENTS_TAB] = "minecraft:select_advancements_tab",
	[PLAY_C_SERVER_DATA] = "minecraft:server_data",
	[PLAY_C_SET_ACTION_BAR_TEXT] = "minecraft:set_action_bar_text",
	[PLAY_C_SET_BORDER_CENTER] = "minecraft:set_border_center",
	[PLAY_C_SET_BORDER_LERP_SIZE] = "minecraft:set_border_lerp_size",
	[PLAY_C_SET_BORDER_SIZE] = "minecraft:set_border_size",
	[PLAY_C_SET_BORDER_WARNING_DELAY] = "minecraft:set_border_warning_delay",
	[PLAY_C_SET_BORDER_WARNING_DISTANCE] = "minecraft:set_border_warning_distance",
	[PLAY_C_SET_CAMERA] = "minecraft:set_camera",
	[PLAY_C_SET_CHUNK_CACHE_CENTER] = "minecraft:set_chunk_cache_center",
	[PLAY_C_SET_CHUNK_CACHE_RADIUS] = "minecraft:set_chunk_cache_radius",
	[PLAY_C_SET_CURSOR_ITEM] = "minecraft:set_cursor_item",
	[PLAY_C_SET_DEFAULT_SPAWN_POSITION] = "minecraft:set_default_spawn_position",
	[PLAY_C_SET_DISPLAY_OBJECTIVE] = "minecraft:set_display_objective",
	[PLAY_C_SET_ENTITY_DATA] = "minecraft:set_entity_data",
	[PLAY_C_SET_ENTITY_LINK] = "minecraft:set_entity_link",
	[PLAY_C_SET_ENTITY_MOTION] = "minecraft:set_entity_motion",
	[PLAY_C_SET_EQUIPMENT] = "minecraft:set_equipment",
	[PLAY_C_SET_EXPERIENCE] = "minecraft:set_experience",
	[PLAY_C_SET_HEALTH] = "minecraft:set_health",
	[PLAY_C_SET_HELD_SLOT] = "minecraft:set_held_slot",
	[PLAY_C_SET_OBJECTIVE] = "minecraft:set_objective",
	[PLAY_C_SET_PASSENGERS] = "minecraft:set_passengers",
	[PLAY_C_SET_PLAYER_INVENTORY] = "minecraft:set_player_inventory",
	[PLAY_C_SET_PLAYER_TEAM] = "minecraft:set_player_team",
	[PLAY_C_SET_SCORE] = "minecraft:set_score",
	[PLAY_C_SET_SIMULATION_DISTANCE] = "minecraft:set_simulation_distance",
	[PLAY_C_SET_SUBTITLE_TEXT] = "minecraft:set_subtitle_text",
	[PLAY_C_SET_TIME] = "minecraft:set_time",
	[PLAY_C_SET_TITLE_TEXT] = "minecraft:set_title_text",
	[PLAY_C_SET_TITLES_ANIMATION] = "minecraft:set_titles_animation",
	[PLAY_C_SOUND_ENTITY] = "minecraft:sound_entity",
	[PLAY_C_SOUND] = "minecraft:sound",
	[PLAY_C_START_CONFIGURATION] = "minecraft:start_configuration",
	[PLAY_C_STOP_SOUND] = "minecraft:stop_sound",
	[PLAY_C_STORE_COOKIE] = "minecraft:store_cookie",
	[PLAY_C_SYSTEM_CHAT] = "minecraft:system_chat",
	[PLAY_C_TAB_LIST] = "minecraft:tab_list",
	[PLAY_C_TAG_QUERY] = "minecraft:tag_query",
	[PLAY_C_TAKE_ITEM_ENTITY] = "minecraft:take_item_entity",
	[PLAY_C_TELEPORT_ENTITY] = "minecraft:teleport_entity",
	[PLAY_C_TEST_INSTANCE_BLOCK_STATUS] = "minecraft:test_instance_block_status",
	[PLAY_C_TICKING_STATE] = "minecraft:ticking_state",
	[PLAY_C_TICKING_STEP] = "minecraft:ticking_step",
	[PLAY_C_TRANSFER] = "minecraft:transfer",
	[PLAY_C_UPDATE_ADVANCEMENTS] = "minecraft:update_advancements",
	[PLAY_C_UPDATE_ATTRIBUTES] = "minecraft:update_attributes",
	[PLAY_C_UPDATE_MOB_EFFECT] = "minecraft:update_mob_effect",
	[PLAY_C_UPDATE_RECIPES] = "minecraft:update_recipes",
	[PLAY_C_UPDATE_TAGS] = "minecraft:update_tags",
	[PLAY_C_PROJECTILE_POWER] = "minecraft:projectile_power",
	[PLAY_C_CUSTOM_REPORT_DETAILS] = "minecraft:custom_report_details",
	[PLAY_C_SERVER_LINKS] = "minecraft:server_links",
};

static char *play_s_packet_names[PLAY_S_NPACKETS] = {
	[PLAY_S_ACCEPT_TELEPORTATION] = "minecraft:accept_teleportation",
	[PLAY_S_BLOCK_ENTITY_TAG_QUERY] = "minecraft:block_entity_tag_query",
	[PLAY_S_BUNDLE_ITEM_SELECTED] = "minecraft:bundle_item_selected",
	[PLAY_S_CHANGE_DIFFICULTY] = "minecraft:change_difficulty",
	[PLAY_S_CHAT_ACK] = "minecraft:chat_ack",
	[PLAY_S_CHAT_COMMAND] = "minecraft:chat_command",
	[PLAY_S_CHAT_COMMAND_SIGNED] = "minecraft:chat_command_signed",
	[PLAY_S_CHAT] = "minecraft:chat",
	[PLAY_S_CHAT_SESSION_UPDATE] = "minecraft:chat_session_update",
	[PLAY_S_CHUNK_BATCH_RECEIVED] = "minecraft:chunk_batch_received",
	[PLAY_S_CLIENT_COMMAND] = "minecraft:client_command",
	[PLAY_S_CLIENT_TICK_END] = "minecraft:client_tick_end",
	[PLAY_S_CLIENT_INFORMATION] = "minecraft:client_information",
	[PLAY_S_COMMAND_SUGGESTION] = "minecraft:command_suggestion",
	[PLAY_S_CONFIGURATION_ACKNOWLEDGED] = "minecraft:configuration_acknowledged",
	[PLAY_S_CONTAINER_BUTTON_CLICK] = "minecraft:container_button_click",
	[PLAY_S_CONTAINER_CLICK] = "minecraft:container_click",
	[PLAY_S_CONTAINER_CLOSE] = "minecraft:container_close",
	[PLAY_S_CONTAINER_SLOT_STATE_CHANGED] = "minecraft:container_slot_state_changed",
	[PLAY_S_COOKIE_RESPONSE] = "minecraft:cookie_response",
	[PLAY_S_CUSTOM_PAYLOAD] = "minecraft:custom_payload",
	[PLAY_S_DEBUG_SAMPLE_SUBSCRIPTION] = "minecraft:debug_sample_subscription",
	[PLAY_S_EDIT_BOOK] = "minecraft:edit_book",
	[PLAY_S_ENTITY_TAG_QUERY] = "minecraft:entity_tag_query",
	[PLAY_S_INTERACT] = "minecraft:interact",
	[PLAY_S_JIGSAW_GENERATE] = "minecraft:jigsaw_generate",
	[PLAY_S_KEEP_ALIVE] = "minecraft:keep_alive",
	[PLAY_S_LOCK_DIFFICULTY] = "minecraft:lock_difficulty",
	[PLAY_S_MOVE_PLAYER_POS] = "minecraft:move_player_pos",
	[PLAY_S_MOVE_PLAYER_POS_ROT] = "minecraft:move_player_pos_rot",
	[PLAY_S_MOVE_PLAYER_ROT] = "minecraft:move_player_rot",
	[PLAY_S_MOVE_PLAYER_STATUS_ONLY] = "minecraft:move_player_status_only",
	[PLAY_S_MOVE_VEHICLE] = "minecraft:move_vehicle",
	[PLAY_S_PADDLE_BOAT] = "minecraft:paddle_boat",
	[PLAY_S_PICK_ITEM_FROM_BLOCK] = "minecraft:pick_item_from_block",
	[PLAY_S_PICK_ITEM_FROM_ENTITY] = "minecraft:pick_item_from_entity",
	[PLAY_S_PING_REQUEST] = "minecraft:ping_request",
	[PLAY_S_PLACE_RECIPE] = "minecraft:place_recipe",
	[PLAY_S_PLAYER_ABILITIES] = "minecraft:player_abilities",
	[PLAY_S_PLAYER_ACTION] = "minecraft:player_action",
	[PLAY_S_PLAYER_COMMAND] = "minecraft:player_command",
	[PLAY_S_PLAYER_INPUT] = "minecraft:player_input",
	[PLAY_S_PLAYER_LOADED] = "minecraft:player_loaded",
	[PLAY_S_PONG] = "minecraft:pong",
	[PLAY_S_RECIPE_BOOK_CHANGE_SETTINGS] = "minecraft:recipe_book_change_settings",
	[PLAY_S_RECIPE_BOOK_SEEN_RECIPE] = "minecraft:recipe_book_seen_recipe",
	[PLAY_S_RENAME_ITEM] = "minecraft:rename_item",
	[PLAY_S_RESOURCE_PACK] = "minecraft:resource_pack",
	[PLAY_S_SEEN_ADVANCEMENTS] = "minecraft:seen_advancements",
	[PLAY_S_SELECT_TRADE] = "minecraft:select_trade",
	[PLAY_S_SET_BEACON] = "minecraft:set_beacon",
	[PLAY_S_SET_CARRIED_ITEM] = "minecraft:set_carried_item",
	[PLAY_S_SET_COMMAND_BLOCK] = "minecraft:set_command_block",
	[PLAY_S_SET_COMMAND_MINECART] = "minecraft:set_command_minecart",
	[PLAY_S_SET_CREATIVE_MODE_SLOT] = "minecraft:set_creative_mode_slot",
	[PLAY_S_SET_JIGSAW_BLOCK] = "minecraft:set_jigsaw_block",
	[PLAY_S_SET_STRUCTURE_BLOCK] = "minecraft:set_structure_block",
	[PLAY_S_SET_TEST_BLOCK] = "minecraft:set_test_block",
	[PLAY_S_SIGN_UPDATE] = "minecraft:sign_update",
	[PLAY_S_SWING] = "minecraft:swing",
	[PLAY_S_TELEPORT_TO_ENTITY] = "minecraft:teleport_to_entity",
	[PLAY_S_TEST_INSTANCE_BLOCK_ACTION] = "minecraft:test_instance_block_action",
	[PLAY_S_USE_ITEM_ON] = "minecraft:use_item_on",
	[PLAY_S_USE_ITEM] = "minecraft:use_item",
};

static struct protocol_info handshake_protocol = {
	.name = "HANDSHAKE",
	.nserverbound = HANDSHAKE_S_NPACKETS,
	.serverbound_names = handshake_s_packet_names,
};

static struct protocol_info status_protocol = {
	.name = "STATUS",
	.nclientbound = STATUS_C_NPACKETS,
	.clientbound_names = status_c_packet_names,
	.nserverbound = STATUS_S_NPACKETS,
	.serverbound_names = status_s_packet_names,
};

static struct protocol_info login_protocol = {
	.name = "LOGIN",
	.nclientbound = LOGIN_C_NPACKETS,
	.clientbound_names = login_c_packet_names,
	.nserverbound = LOGIN_S_NPACKETS,
	.serverbound_names = login_s_packet_names,
};

static struct protocol_info config_protocol = {
	.name = "CONFIG",
	.nclientbound = CONFIG_C_NPACKETS,
	.clientbound_names = config_c_packet_names,
	.nserverbound = CONFIG_S_NPACKETS,
	.serverbound_names = config_s_packet_names,
};

static struct protocol_info play_protocol = {
	.name = "PLAY",
	.nclientbound = PLAY_C_NPACKETS,
	.clientbound_names = play_c_packet_names,
	.nserverbound = PLAY_S_NPACKETS,
	.serverbound_names = play_s_packet_names,
};

enum {
	HANDSHAKE_STATUS = 1,
	HANDSHAKE_LOGIN = 2,
	HANDSHAKE_TRANSFER = 3,
};

enum {
	TELEPORT_REL_X = 1 << 0,
	TELEPORT_REL_Y = 1 << 1,
	TELEPORT_REL_Z = 1 << 2,
	TELEPORT_REL_YAW = 1 << 3,
	TELEPORT_REL_PITCH = 1 << 4,
	TELEPORT_REL_XVEL = 1 << 5,
	TELEPORT_REL_YVEL = 1 << 6,
	TELEPORT_REL_ZVEL = 1 << 7,
	TELEPORT_ROT_VEL = 1 << 8,
};

enum {
	RESOURCE_PACK_LOADED,
	RESOURCE_PACK_DECLINED,
	RESOURCE_PACK_DOWNLOAD_FAILED,
	RESOURCE_PACK_ACCEPTED,
	RESOURCE_PACK_DOWNLOADED,
	RESOURCE_PACK_INVALID_URL,
	RESOURCE_PACK_LOAD_FAILED,
	RESOURCE_PACK_DISCARDED,
};

static char *host;
static char *port = "25565";
static char *nameprefix = "bot";
static i32 nclients = 10;
static i64 wakeup_interval = 1000000; // ns
static f64 spam_rate = 0.0; // total messages per second
static bool shuffle_clients = false;

static usize addrlen;
static struct sockaddr_storage addr;

static char help[] =
	"Usage: %s [options] address [port]\n"
	"\n"
	"-c count   Number of simultaneous connections to open (default: 10)\n"
	"-n prefix  Prefix for generated player names (default: bot)\n"
	"-r rate    Wakeups per second (default: 1000)\n"
	"-s rate    Spam messages per second (total across all connections)\n"
	"-z         Periodically shuffle ticking order of clients\n";

static void configure(int argc, char **argv) {
	long inum;
	f64 fnum;
	char *endptr;
	signed char opt;
	while ((opt = getopt(argc, argv, ":hc:n:r:s:z")) != -1) switch (opt) {
	case '?':
		die("unrecognized option -%c", optopt);
	case ':':
		die("missing argument to option -%c", optopt);
	case 'h':
		printf(help, argv[0]);
		exit(0);
	case 'c':
		errno = 0;
		inum = strtol(optarg, &endptr, 0);
		if (endptr == optarg || *endptr != '\0' || errno || inum < 0 || inum > INT32_MAX)
			die("argument to -c is not a number in the accepted range");
		nclients = inum;
		break;
	case 'n':
		nameprefix = optarg;
		break;
	case 'r':
		errno = 0;
		fnum = strtod(optarg, &endptr);
		if (endptr == optarg || *endptr != '\0' || errno || fnum < 0 || fnum == HUGE_VAL)
			die("argument to -r is not a number in the accepted range");
		wakeup_interval = 1000000000.0 / fnum;
		break;
	case 's':
		errno = 0;
		fnum = strtod(optarg, &endptr);
		if (endptr == optarg || *endptr != '\0' || errno || fnum < 0 || fnum == HUGE_VAL)
			die("argument to -r is not a number in the accepted range");
		spam_rate = fnum;
		break;
	case 'z':
		shuffle_clients = true;
		break;
	default:
		assert(0);
	}

	if (optind == argc)
		die("no server address specified");
	host = argv[optind++];
	if (optind != argc)
		port = argv[optind++];
	if (optind != argc)
		die("too many arguments");
}

enum client_state {
	CLIENT_FREE,
	CLIENT_LOGIN,
	CLIENT_CONFIG,
	CLIENT_PLAY,
};

struct protocol_info *client_states_protocol[] = {
	[CLIENT_FREE] = NULL,
	[CLIENT_LOGIN] = &login_protocol,
	[CLIENT_CONFIG] = &config_protocol,
	[CLIENT_PLAY] = &play_protocol,
};

enum client_login_substate {
	CLIENT_LOGIN_HELLO,
	CLIENT_LOGIN_ACK,
};

struct sendbuf {
	struct sendbuf *next;
	usize len;
	u8 data[];
};

struct client {
	u8 state, substate;

	i32 entid;

	u32 connected : 1;
	u32 ping_in_flight : 1;
	u32 ping_overdue : 1;
	u32 ping_reset : 1;

	i32 len, lenlen, recvd;
	u8 *recvbuf;

	usize sent;
	struct sendbuf *sendbufs, *lastsendbuf;

	f64 x, y, z;
	f32 yaw, pitch;

	i64 chunk_batch_start;
	i32 nchunks;
	u32 nbatch_chunks;

	u64 ping_payload;
	u64 last_ping;
	u64 rttmin, rttmax, rttsum;
	u64 nrtts;

	char name[17];
};

static struct client *clients; // [nclients]

static struct pollfd *pollfds; // [nclients]

static void remove_client(int clientid);

static struct enc *begin_send(i32 packetid);
static void send_packet(int clientid);
static void finish_send(void);

static i64 tick_interval = 50000000; // ns
static i64 tick_catchup_limit = 200000000; // ns

static i64 now; // ns

static i64 cur_tick; // ns
static i64 cur_wakeup; // ns

static i32 clients_ticked;

static i64 tick_lag; // ns
static i64 tick_lag_duration; // ns
static i64 tick_lag_last_update; // ns

static i64 stat_interval = 1000000000; // ns
static i64 cur_stat; // ns

static void report_stats(void) {
	if (tick_lag != 0) {
		fprintf(stderr,
			"can't keep up! lagged %"PRIu64".%03"PRIu64"s over the course of %"PRIu64".%03"PRIu64"s\n",
			tick_lag / 1000000000,
			tick_lag / 1000000 % 1000,
			tick_lag_duration / 1000000000,
			tick_lag_duration / 1000000 % 1000);
		tick_lag = 0;
		tick_lag_duration = 0;
	}

	i32 nconnect = 0;
	i32 nlogin = 0;
	i32 nconfig = 0;
	i32 nplay = 0;
	i32 nclosed = 0;

	i32 nchunksmin = INT32_MAX;
	i32 nchunksmax = INT32_MIN;
	i64 nchunkssum = 0;

	u64 rttmin = UINT64_MAX;
	u64 rttmax = 0;
	u64 rttsum = 0;
	u64 nrtts = 0;

	u64 inflightmax = 0;

	for (i32 i = 0; i < nclients; ++i) {
		struct client *client = &clients[i];

		if (!client->connected) {
			++nconnect;
		} else switch (client->state) {
		case CLIENT_FREE: ++nclosed; break;
		case CLIENT_LOGIN: ++nlogin; break;
		case CLIENT_CONFIG: ++nconfig; break;
		case CLIENT_PLAY: ++nplay; break;
		}

		if (client->nchunks < nchunksmin)
			nchunksmin = client->nchunks;
		if (client->nchunks > nchunksmax)
			nchunksmax = client->nchunks;
		nchunkssum += client->nchunks;
		if (client->rttmin < rttmin)
			rttmin = client->rttmin;
		if (client->rttmax > rttmax)
			rttmax = client->rttmax;
		rttsum += client->rttsum;
		nrtts += client->nrtts;
		client->ping_reset = true;
		if (client->ping_in_flight) {
			if (now - client->last_ping > inflightmax)
				inflightmax = now - client->last_ping;
		}
	}

	if (!nchunkssum) {
		nchunksmin = 0;
		nchunksmax = 0;
	}

	fprintf(stderr, "status: %"PRIi32" connecting, "
		"%"PRIi32" logging in, %"PRIi32" configuring, "
		"%"PRIi32" in game, %"PRIi32" closed\n",
		nconnect, nlogin, nconfig, nplay, nclosed);

	fprintf(stderr, "loaded chunks min/max/avg: %"PRIi32"/%"PRIi32"/%"PRIi32"\n",
			nchunksmin, nchunksmax, (i32)(nchunkssum / nclients));

	if (nrtts != 0) {
		u64 rttavg = rttsum / nrtts;
		fprintf(stderr, "rtt min/max/avg: "
			"%"PRIu64".%03"PRIu64"/"
			"%"PRIu64".%03"PRIu64"/"
			"%"PRIu64".%03"PRIu64" ms, "
			"in flight max: %"PRIu64".%03"PRIu64" ms\n",
			rttmin / 1000000, rttmin / 1000 % 1000,
			rttmax / 1000000, rttmax / 1000 % 1000,
			rttavg / 1000000, rttavg / 1000 % 1000,
			inflightmax / 1000000, inflightmax / 1000 % 1000);
	} else {
		fprintf(stderr, "rtt min/max/avg: n/a, "
			"in flight max: %"PRIu64".%03"PRIu64" ms\n",
			inflightmax / 1000000, inflightmax / 1000 % 1000);
	}

	if (shuffle_clients) {
		for (i32 i = 0; i < nclients - 2; ++i) {
			i32 j = i + 1 + random() % (nclients - i - 1);
			struct client tmpclient = clients[i];
			struct pollfd tmppollfd = pollfds[i];
			clients[i] = clients[j];
			pollfds[i] = pollfds[j];
			clients[j] = tmpclient;
			pollfds[j] = tmppollfd;
		}
	}
}

static void send_ping(i32 clientid) {
	struct client *client = &clients[clientid];

	assert(!client->ping_in_flight);

	client->ping_in_flight = true;
	client->ping_payload = random();
	client->last_ping = now;

	struct enc *e = begin_send(PLAY_S_PING_REQUEST);
	enc_u64(e, client->ping_payload);
	send_packet(clientid);
	finish_send();
}


static void tick_clients(i32 start, i32 end) {
	/*
	fprintf(stderr, "tick %"PRIi32" clients, [%"PRIi32",%"PRIi32")\n",
		end - start, start, end);
	*/

	struct enc *e;

	for (i32 clientid = start; clientid < end; ++clientid) {
		struct client *client = &clients[clientid];

		if (client->state != CLIENT_PLAY)
			continue;

		client->x += rand() % 3 - 1;
		client->z += rand() % 3 - 1;

		e = begin_send(PLAY_S_MOVE_PLAYER_POS);
		enc_f64(e, client->x);
		enc_f64(e, client->y);
		enc_f64(e, client->z);
		enc_i8(e, true);
		send_packet(clientid);
		finish_send();

		/*
		e = begin_send(PLAY_S_PLAYER_ACTION);
		enc_v32(e, PLAYER_ACTION_DROP_ITEM);
		enc_u64(e, 0);
		enc_u8(e, 0);
		enc_v32(e, 0);
		send_packet(clientid);
		finish_send();
		*/

		if (!client->ping_in_flight) {
			send_ping(clientid);
		} else {
			client->ping_overdue = true;
		}


		if (spam_rate) {
			f64 r = (f64)rand() / RAND_MAX * (nclients / (spam_rate * (tick_interval / 1000000000.0)));
			if (r < 1) {
				e = begin_send(PLAY_S_CHAT);
				enc_str(e, "quiet, please!");
				enc_u64(e, 0);
				enc_u64(e, 0);
				enc_u8(e, 0);
				enc_u8(e, 0);
				enc_u8(e, 0);
				enc_u8(e, 0);
				enc_u8(e, 0);
				send_packet(clientid);
				finish_send();
			}
		}
	}
}

static bool handle_play_packet(int clientid, i32 packetid, struct dec *d) {
	struct client *client = &clients[clientid];

	struct enc *e;

	switch (packetid) {
	case PLAY_C_KEEP_ALIVE: {
		u64 payload;

		if (!dec_u64(d, &payload))
			return false;
		if (!dec_end(d))
			return false;

		e = begin_send(PLAY_S_KEEP_ALIVE);
		enc_u64(e, payload);
		send_packet(clientid);
		finish_send();

		return true;
	}
	case PLAY_C_PONG_RESPONSE: {
		u64 payload;

		if (!dec_u64(d, &payload))
			return false;
		if (!dec_end(d))
			return false;

		if (!client->ping_in_flight) {
			fprintf(stderr, "spurious pong received (no ping in flight). rtt may be inaccurate.\n");
			return true;
		}

		if (payload != client->ping_payload) {
			fprintf(stderr, "spurious pong received (payload mismatch: expected=%"PRIi64", received=%"PRIi64"). rtt may be inaccurate.\n",
				client->ping_payload, payload);
			return true;
		}

		client->ping_in_flight = false;

		if (client->ping_reset) {
			client->ping_reset = 0;
			client->rttmin = UINT64_MAX;
			client->rttmax = 0;
			client->rttsum = 0;
			client->nrtts = 0;
		}

		u64 rtt = now - client->last_ping;
		if (rtt < client->rttmin)
			client->rttmin = rtt;
		if (rtt > client->rttmax)
			client->rttmax = rtt;
		client->rttsum += rtt;
		++client->nrtts;

		if (client->ping_overdue) {
			send_ping(clientid);
			client->ping_overdue = false;
		}

		return true;
	}
	case PLAY_C_LEVEL_CHUNK_WITH_LIGHT:
		++client->nchunks;
		return true;
	case PLAY_C_FORGET_LEVEL_CHUNK:
		--client->nchunks;
		return true;
	case PLAY_C_CHUNK_BATCH_START:
		client->chunk_batch_start = now;
		client->nbatch_chunks = 0;
		return true;
	case PLAY_C_CHUNK_BATCH_FINISHED: {
		i64 dt = now - client->chunk_batch_start;
		f32 chunks_per_tick = 25000000.0 / dt;

		e = begin_send(PLAY_S_CHUNK_BATCH_RECEIVED);
		enc_f32(e, chunks_per_tick);
		send_packet(clientid);
		finish_send();

		return true;
	}
	case PLAY_C_GAME_EVENT: {
		u8 event;

		if (!dec_u8(d, &event))
			return false;
		// don't care about the rest of this.

		e = begin_send(PLAY_S_PLAYER_LOADED);
		send_packet(clientid);
		finish_send();

		return true;
	}
	case PLAY_C_PLAYER_POSITION: {
		i32 teleport_id;
		f64 x, y, z;
		f64 xvel, yvel, zvel;
		f32 yaw, pitch;
		u32 flags;

		if (!dec_v32(d, &teleport_id))
			return false;
		if (!dec_f64(d, &x))
			return false;
		if (!dec_f64(d, &y))
			return false;
		if (!dec_f64(d, &z))
			return false;
		if (!dec_f64(d, &xvel))
			return false;
		if (!dec_f64(d, &yvel))
			return false;
		if (!dec_f64(d, &zvel))
			return false;
		if (!dec_f32(d, &yaw))
			return false;
		if (!dec_f32(d, &pitch))
			return false;
		if (!dec_u32(d, &flags))
			return false;
		if (!dec_end(d))
			return false;

		if (flags & TELEPORT_REL_X)
			x += client->x;
		if (flags & TELEPORT_REL_Y)
			y += client->y;
		if (flags & TELEPORT_REL_Z)
			z += client->z;
		if (flags & TELEPORT_REL_YAW)
			yaw += client->yaw;
		if (flags & TELEPORT_REL_PITCH)
			pitch += client->pitch;

		client->x = x;
		client->y = y;
		client->z = z;
		client->yaw = yaw;
		client->pitch = pitch;

		e = begin_send(PLAY_S_ACCEPT_TELEPORTATION);
		enc_v32(e, teleport_id);
		send_packet(clientid);
		finish_send();

		return true;
	}
	case PLAY_C_ADD_ENTITY:
	case PLAY_C_BUNDLE_DELIMITER:
	case PLAY_C_DISGUISED_CHAT:
	case PLAY_C_ENTITY_POSITION_SYNC:
	case PLAY_C_LOGIN:
	case PLAY_C_PLAYER_ABILITIES:
	case PLAY_C_PLAYER_INFO_REMOVE:
	case PLAY_C_PLAYER_INFO_UPDATE:
	case PLAY_C_REMOVE_ENTITIES:
	case PLAY_C_ROTATE_HEAD:
	case PLAY_C_SET_ENTITY_DATA:
	case PLAY_C_SET_TIME:
	case PLAY_C_SYSTEM_CHAT:
	case PLAY_C_MOVE_ENTITY_POS:
	case PLAY_C_MOVE_ENTITY_POS_ROT:
	case PLAY_C_MOVE_ENTITY_ROT:
		return true;
	case PLAY_C_ANIMATE:
	case PLAY_C_AWARD_STATS:
	case PLAY_C_BLOCK_CHANGED_ACK:
	case PLAY_C_BLOCK_DESTRUCTION:
	case PLAY_C_BLOCK_ENTITY_DATA:
	case PLAY_C_BLOCK_EVENT:
	case PLAY_C_BLOCK_UPDATE:
	case PLAY_C_BOSS_EVENT:
	case PLAY_C_CHANGE_DIFFICULTY:
	case PLAY_C_CHUNKS_BIOMES:
	case PLAY_C_CLEAR_TITLES:
	case PLAY_C_COMMAND_SUGGESTIONS:
	case PLAY_C_COMMANDS:
	case PLAY_C_CONTAINER_CLOSE:
	case PLAY_C_CONTAINER_SET_CONTENT:
	case PLAY_C_CONTAINER_SET_DATA:
	case PLAY_C_CONTAINER_SET_SLOT:
	case PLAY_C_COOKIE_REQUEST:
	case PLAY_C_COOLDOWN:
	case PLAY_C_CUSTOM_CHAT_COMPLETIONS:
	case PLAY_C_CUSTOM_PAYLOAD:
	case PLAY_C_DAMAGE_EVENT:
	case PLAY_C_DEBUG_SAMPLE:
	case PLAY_C_DELETE_CHAT:
	case PLAY_C_DISCONNECT:
	case PLAY_C_ENTITY_EVENT:
	case PLAY_C_EXPLODE:
	case PLAY_C_HORSE_SCREEN_OPEN:
	case PLAY_C_HURT_ANIMATION:
	case PLAY_C_INITIALIZE_BORDER:
	case PLAY_C_LEVEL_EVENT:
	case PLAY_C_LEVEL_PARTICLES:
	case PLAY_C_LIGHT_UPDATE:
	case PLAY_C_MAP_ITEM_DATA:
	case PLAY_C_MERCHANT_OFFERS:
	case PLAY_C_MOVE_MINECART_ALONG_TRACK:
	case PLAY_C_MOVE_VEHICLE:
	case PLAY_C_OPEN_BOOK:
	case PLAY_C_OPEN_SCREEN:
	case PLAY_C_OPEN_SIGN_EDITOR:
	case PLAY_C_PING:
	case PLAY_C_PLACE_GHOST_RECIPE:
	case PLAY_C_PLAYER_CHAT:
	case PLAY_C_PLAYER_COMBAT_END:
	case PLAY_C_PLAYER_COMBAT_ENTER:
	case PLAY_C_PLAYER_COMBAT_KILL:
	case PLAY_C_PLAYER_LOOK_AT:
	case PLAY_C_PLAYER_ROTATION:
	case PLAY_C_RECIPE_BOOK_ADD:
	case PLAY_C_RECIPE_BOOK_REMOVE:
	case PLAY_C_RECIPE_BOOK_SETTINGS:
	case PLAY_C_REMOVE_MOB_EFFECT:
	case PLAY_C_RESET_SCORE:
	case PLAY_C_RESOURCE_PACK_POP:
	case PLAY_C_RESOURCE_PACK_PUSH:
	case PLAY_C_RESPAWN:
	case PLAY_C_SECTION_BLOCKS_UPDATE:
	case PLAY_C_SELECT_ADVANCEMENTS_TAB:
	case PLAY_C_SERVER_DATA:
	case PLAY_C_SET_ACTION_BAR_TEXT:
	case PLAY_C_SET_BORDER_CENTER:
	case PLAY_C_SET_BORDER_LERP_SIZE:
	case PLAY_C_SET_BORDER_SIZE:
	case PLAY_C_SET_BORDER_WARNING_DELAY:
	case PLAY_C_SET_BORDER_WARNING_DISTANCE:
	case PLAY_C_SET_CAMERA:
	case PLAY_C_SET_CHUNK_CACHE_CENTER:
	case PLAY_C_SET_CHUNK_CACHE_RADIUS:
	case PLAY_C_SET_CURSOR_ITEM:
	case PLAY_C_SET_DEFAULT_SPAWN_POSITION:
	case PLAY_C_SET_DISPLAY_OBJECTIVE:
	case PLAY_C_SET_ENTITY_LINK:
	case PLAY_C_SET_ENTITY_MOTION:
	case PLAY_C_SET_EQUIPMENT:
	case PLAY_C_SET_EXPERIENCE:
	case PLAY_C_SET_HEALTH:
	case PLAY_C_SET_HELD_SLOT:
	case PLAY_C_SET_OBJECTIVE:
	case PLAY_C_SET_PASSENGERS:
	case PLAY_C_SET_PLAYER_INVENTORY:
	case PLAY_C_SET_PLAYER_TEAM:
	case PLAY_C_SET_SCORE:
	case PLAY_C_SET_SIMULATION_DISTANCE:
	case PLAY_C_SET_SUBTITLE_TEXT:
	case PLAY_C_SET_TITLE_TEXT:
	case PLAY_C_SET_TITLES_ANIMATION:
	case PLAY_C_SOUND_ENTITY:
	case PLAY_C_SOUND:
	case PLAY_C_START_CONFIGURATION:
	case PLAY_C_STOP_SOUND:
	case PLAY_C_STORE_COOKIE:
	case PLAY_C_TAB_LIST:
	case PLAY_C_TAG_QUERY:
	case PLAY_C_TAKE_ITEM_ENTITY:
	case PLAY_C_TELEPORT_ENTITY:
	case PLAY_C_TICKING_STATE:
	case PLAY_C_TICKING_STEP:
	case PLAY_C_TRANSFER:
	case PLAY_C_UPDATE_ADVANCEMENTS:
	case PLAY_C_UPDATE_ATTRIBUTES:
	case PLAY_C_UPDATE_MOB_EFFECT:
	case PLAY_C_UPDATE_RECIPES:
	case PLAY_C_UPDATE_TAGS:
	case PLAY_C_PROJECTILE_POWER:
	case PLAY_C_CUSTOM_REPORT_DETAILS:
	case PLAY_C_SERVER_LINKS:
		/*
		fprintf(stderr, "< unhandled play packet %s [%"PRIi32"]\n",
			play_c_packet_names[packetid], packetid);
		*/
		return true;
	default:
		dec_error(d, NULL, "unknown play packet id");
		return false;
	}
}

static bool handle_packet(int clientid, i32 packetid, struct dec *d) {
	struct client *client = &clients[clientid];

	struct enc *e;

	switch (client->state) {
	case CLIENT_LOGIN:
		switch (packetid) {
		case LOGIN_C_LOGIN_FINISHED: {
			if (!dec_advance(d, 16))
				return false;
			if (!dec_strncpy(d, client->name, sizeof(client->name)))
				return false;
			// don't care about the rest of this.

			e = begin_send(LOGIN_S_LOGIN_ACKNOWLEDGED);
			send_packet(clientid);
			finish_send();

			client->state = CLIENT_CONFIG;

			return true;
		}
		case LOGIN_C_HELLO:
		case LOGIN_C_LOGIN_DISCONNECT:
		case LOGIN_C_LOGIN_COMPRESSION:
		case LOGIN_C_CUSTOM_QUERY:
		case LOGIN_C_COOKIE_REQUEST:
			fprintf(stderr, "< unhandled login packet %s [%"PRIi32"]\n",
				login_c_packet_names[packetid], packetid);
			return true;
		}
		break;
	case CLIENT_CONFIG:
		switch (packetid) {
		case CONFIG_C_SELECT_KNOWN_PACKS: {
			e = begin_send(CONFIG_S_SELECT_KNOWN_PACKS);
			enc_copy(e, d->ptr, d->limit - d->ptr);
			send_packet(clientid);
			finish_send();

			return true;
		}
		case CONFIG_C_RESOURCE_PACK_PUSH: {
			u64 uuid[2];

			if (!dec_u64(d, &uuid[1]))
				return false;
			if (!dec_u64(d, &uuid[0]))
				return false;
			// don't care abort the rest of this.

			e = begin_send(CONFIG_S_RESOURCE_PACK);
			enc_u64(e, uuid[1]);
			enc_u64(e, uuid[0]);
			enc_v32(e, RESOURCE_PACK_ACCEPTED);
			send_packet(clientid);
			finish_send();

			e = begin_send(CONFIG_S_RESOURCE_PACK);
			enc_u64(e, uuid[1]);
			enc_u64(e, uuid[0]);
			enc_v32(e, RESOURCE_PACK_LOADED);
			send_packet(clientid);
			finish_send();

			return true;
		}
		case CONFIG_C_FINISH_CONFIGURATION: {
			if (!dec_end(d))
				return false;

			client->state = CLIENT_PLAY;

			e = begin_send(CONFIG_S_FINISH_CONFIGURATION);
			send_packet(clientid);
			finish_send();

			return true;
		}
		case CONFIG_C_REGISTRY_DATA:
		case CONFIG_C_UPDATE_TAGS:
		case CONFIG_C_CUSTOM_PAYLOAD:
		case CONFIG_C_UPDATE_ENABLED_FEATURES:
			return true;
		case CONFIG_C_COOKIE_REQUEST:
		case CONFIG_C_DISCONNECT:
		case CONFIG_C_KEEP_ALIVE:
		case CONFIG_C_PING:
		case CONFIG_C_RESET_CHAT:
		case CONFIG_C_RESOURCE_PACK_POP:
		case CONFIG_C_STORE_COOKIE:
		case CONFIG_C_TRANSFER:
		case CONFIG_C_CUSTOM_REPORT_DETAILS:
		case CONFIG_C_SERVER_LINKS:
			fprintf(stderr, "< unhandled config packet %s [%"PRIi32"]\n",
				config_c_packet_names[packetid], packetid);
			return true;
		}
		break;
	case CLIENT_PLAY:
		return handle_play_packet(clientid, packetid, d);
	default:
		assert(false);
	}

	dec_error(d, NULL, "packet unexpected in this state");
	return false;
}

static void remove_client(int clientid) {
	struct client *client = &clients[clientid];

	if (client->state == CLIENT_FREE)
		return;
	fprintf(stderr, "%s: connection lost (state=%d)\n", client->name, client->state);

	client->state = CLIENT_FREE;

	if (client->recvbuf) {
		free(client->recvbuf);
		client->recvbuf = NULL;
	}

	while (client->sendbufs) {
		struct sendbuf *next = client->sendbufs->next;
		free(client->sendbufs);
		client->sendbufs = next;
	}
	client->lastsendbuf = NULL;

	struct linger linger = {true, 0};
	if (setsockopt(pollfds[clientid].fd,
		SOL_SOCKET, SO_LINGER,
		&linger, sizeof(linger)) < 0)
	{
		perror("setsockopt(SO_LINGER)");
	}
	if (close(pollfds[clientid].fd) < 0)
		perror("close");

	pollfds[clientid] = (struct pollfd){.fd = -1};
}

static void recv_packet(int clientid, u8 *ptr, u8 *limit) {
	struct client *client = &clients[clientid];

	//pretty_hexdump(stderr, "< ", ptr, limit);

	struct protocol_info *protoinfo = client_states_protocol[client->state];
	char *packetname = NULL;
	i32 packetid = -1;

	struct dec d = {.ptr = ptr, .limit = limit};

	if (!dec_v32(&d, &packetid))
		goto error;

	if (packetid < protoinfo->nclientbound)
		packetname = protoinfo->clientbound_names[packetid];
	if (!packetname)
		packetname = "(unknown)";
	//fprintf(stderr, "< %s/%s [%"PRIi32"]\n", protoinfo->name, packetname, packetid);

	if (!handle_packet(clientid, packetid, &d))
		goto error;

	return;

error:
	if (!packetname)
		packetname = "(unknown)";
	if (d.errpos) {
		fprintf(stderr, "< invalid packet (type %s/%s [%"PRIi32"/%#"PRIx32"], length %zu/%#zx, offset %zu/%#zx): %s\n",
			protoinfo->name, packetname, packetid, packetid,
			limit - ptr, limit - ptr,
			d.errpos - ptr, d.errpos - ptr, d.error);
	} else {
		fprintf(stderr, "< invalid packet (type %s/%s [%"PRIi32"/%#"PRIx32"], length %zu/%#zx): %s\n",
			protoinfo->name, packetname, packetid, packetid,
			limit - ptr, limit - ptr, d.error);
	}
	remove_client(clientid);
	return;
}

static bool recv_frame(int clientid, u8 **ptr, u8 *limit) {
	struct client *client = &clients[clientid];

	if (client->len && !client->lenlen)
		goto data;

	for (; client->lenlen < 21; client->lenlen += 7) {
		if (*ptr == limit)
			return false;
		u8 b = *(*ptr)++;
		client->len |= (b & 0x7f) << client->lenlen;
		if (!(b & 0x80))
			goto data;
	}

	fprintf(stderr, "< packet too large\n");
	remove_client(clientid);
	return false;

data:

	client->lenlen = 0;

	if (limit - *ptr < client->len)
		return false;

	recv_packet(clientid, *ptr, *ptr + client->len);

	*ptr += client->len;
	client->len = 0;

	return true;
}

static void poll_client_in(int clientid) {
	if (!(pollfds[clientid].revents & POLLIN))
		return;

	struct client *client = &clients[clientid];

	static u8 tmpbuf[BUFSIZ];
	isize recvd;

	if (client->recvbuf) {
		struct iovec iov[2] = {
			{client->recvbuf + client->recvd,
				client->len - client->recvd},
			{tmpbuf, BUFSIZ},
		};
		recvd = readv(pollfds[clientid].fd, iov, 2);
	} else {
		recvd = read(pollfds[clientid].fd, tmpbuf, BUFSIZ);
	}

	if (recvd < 0) {
		if (errno == EAGAIN || errno == EWOULDBLOCK)
			return;
		if (errno != ECONNRESET)
			perror(client->recvbuf ? "readv" : "read");
		remove_client(clientid);
		return;
	}

	if (recvd == 0) {
		remove_client(clientid);
		return;
	}

	if (client->recvbuf) {
		if (recvd < client->len - client->recvd) {
			client->recvd += recvd;
			return;
		}
		recvd -= client->len - client->recvd;
		recv_packet(clientid,
			client->recvbuf,
			client->recvbuf + client->len);
		if (client->state == CLIENT_FREE)
			return;
		free(client->recvbuf);
		client->recvbuf = 0;
		client->len = 0;
	}

	u8 *ptr = tmpbuf;
	u8 *limit = tmpbuf + recvd;

	while (recv_frame(clientid, &ptr, limit))
		if (client->state == CLIENT_FREE)
			return;

	if (client->state == CLIENT_FREE)
		return;

	if (client->len && !client->lenlen) {
		client->recvbuf = malloc(client->len);
		if (!client->recvbuf)
			dieerror("malloc");
		client->recvd = limit - ptr;
		memcpy(client->recvbuf, ptr, limit - ptr);
	}
}

static u8 send_buf[1 << 21];
static struct enc send_enc;

static struct enc *begin_send(i32 packetid) {
	assert(!send_enc.ptr);
	send_enc = (struct enc){
		.ptr = send_buf,
		.limit = send_buf + sizeof(send_buf),
	};
	//fprintf(stderr, "> [%"PRIi32"]\n", packetid);
	enc_v32(&send_enc, packetid);
	return &send_enc;
}

static void send_packet(int clientid) {
	struct client *client = &clients[clientid];

	if (client->state == CLIENT_FREE)
		return;

	i32 len = send_enc.ptr - send_buf;

	if (send_enc.trunc || len >= ((i32)1 << 21)) {
		fprintf(stderr, "> packet too large to send\n");
		remove_client(clientid);
		return;
	}

	if (len > 0x100) {
		//pretty_hexdump(stderr, "> ", send_buf, send_buf + 0x100);
		//fprintf(stderr, "> ... 0x%"PRIx32" more bytes\n", len - 0x100);
	} else {
		//pretty_hexdump(stderr, "> ", send_buf, send_enc.ptr);
	}

	struct sendbuf *buf = malloc(sizeof(struct sendbuf) + len + 3);
	if (!buf)
		dieerror("malloc");

	u8 *ptr = buf->data;
	i32 len_ = len;
	do {
		u8 b = len_ & 0x7f;
		len_ >>= 7;
		if (len_)
			b |= 0x80;
		*ptr++ = b;
	} while (len_);
	buf->next = NULL;
	buf->len = ptr - buf->data + len;
	memcpy(ptr, send_buf, len);

	if (client->lastsendbuf)
		client->lastsendbuf->next = buf;
	else
		client->sendbufs = buf;
	client->lastsendbuf = buf;

	pollfds[clientid].events |= POLLOUT;
}

static void finish_send(void) {
	send_enc.ptr = NULL;
}

static void poll_client_out(int clientid) {
	if (!(pollfds[clientid].revents & POLLOUT))
		return;

	struct client *client = &clients[clientid];

	if (!client->connected) {
		int err;
		socklen_t optlen = sizeof(err);
		if (getsockopt(pollfds[clientid].fd, SOL_SOCKET, SO_ERROR, &err, &optlen) < 0) {
			perror("getsockopt(SO_ERROR)");
			remove_client(clientid);
			return;
		}
		if (err) {
			errno = err;
			perror("connect");
			remove_client(clientid);
			return;
		}

		client->connected = true;

		// fallthrough
	}

	while (client->sendbufs) {
		usize len = client->sendbufs->len;
		isize sent = write(pollfds[clientid].fd,
			client->sendbufs->data + client->sent,
			len - client->sent);
		if (sent < 0) {
			if (errno == EAGAIN || errno == EWOULDBLOCK)
				return;
			if (errno != EPIPE && errno != ECONNRESET)
				perror("write");
			remove_client(clientid);
			return;
		}
		client->sent += sent;
		if (client->sent < len)
			return;
		struct sendbuf *next = client->sendbufs->next;
		free(client->sendbufs);
		client->sendbufs = next;
		client->sent = 0;
	}

	client->lastsendbuf = NULL;
	pollfds[clientid].events &= ~POLLOUT;
}

static void connect_client(int clientid) {
	char *errprefix;

	int sock = socket(addr.ss_family, SOCK_STREAM, 0);
	if (sock < 0) {
		errprefix = "socket";
		goto fail;
	}
	int flags = fcntl(sock, F_GETFL);
	if (flags < 0) {
		errprefix = "fcntl(F_GETFL)";
		goto fail;
	}
	if (fcntl(sock, F_SETFL, flags | O_NONBLOCK) < 0) {
		errprefix = "fcntl(F_SETFL)";
		goto fail;
	}
	if (addr.ss_family == AF_INET || addr.ss_family == AF_INET6) {
		int nodelay = 1;
		if (setsockopt(sock, IPPROTO_TCP, TCP_NODELAY, &nodelay, sizeof(nodelay)) < 0) {
			errprefix = "setsockopt(TCP_NODELAY)";
			goto fail;
		}
	}
	if (connect(sock, (struct sockaddr *)&addr, addrlen) < 0) {
		// XXX: Linux's behavior with non-blocking UNIX domain sockets is
		// completely absurd: instead of EINPROGRESS we'll get EAGAIN when the
		// queue is full, but if we tried to handle that case here we'd soon
		// receive ENOTCONN and die. Not much we can do here it seems, other
		// than blocking connect() I guess?
		if (errno != EINPROGRESS) {
			perror("connect");
			remove_client(clientid);
			return;
		}
	}

	pollfds[clientid] = (struct pollfd){
		.fd = sock,
		.events = POLLIN | POLLOUT,
	};
	struct client *client = &clients[clientid];
	*client = (struct client){
		.state = CLIENT_LOGIN,
		.connected = false,
		.ping_reset = true,
		.rttmin = UINT64_MAX,
	};

	snprintf(client->name, sizeof(client->name),
		"%s%"PRIi32, nameprefix, clientid);

	struct enc *e;

	e = begin_send(HANDSHAKE_S_INTENTION);
	enc_v32(e, 770);
	enc_str(e, host);
	enc_u16(e, 25565);
	enc_v32(e, HANDSHAKE_LOGIN);
	send_packet(clientid);
	finish_send();

	e = begin_send(LOGIN_S_HELLO);
	enc_str(e, client->name);
	enc_advance(e, 16);
	send_packet(clientid);
	finish_send();

	return;

fail:
	perror(errprefix);
	if (sock >= 0) {
		if (close(sock) < 0)
			perror("close");
	}
}

static void poll_client(int clientid) {
	struct client *client = &clients[clientid];
	if (client->state == CLIENT_FREE) {
		connect_client(clientid);
	}
	poll_client_out(clientid);
	poll_client_in(clientid);
}

int main(int argc, char **argv) {
	static char stderrbuf[BUFSIZ];
	if (setvbuf(stderr, stderrbuf, _IOLBF, BUFSIZ) < 0)
		dieerror("setvbuf(stderr)");

	struct sigaction sigact = {
		.sa_handler = SIG_IGN,
	};
	if (sigaction(SIGPIPE, &sigact, NULL))
		dieerror("sigaction(SIGPIPE)");

	configure(argc, argv);

	int res;

	struct addrinfo hints = {
		.ai_family = AF_UNSPEC,
		.ai_socktype = SOCK_STREAM,
		.ai_protocol = 0,
		.ai_flags = 0,
	};
	/*
	struct sockaddr_un unaddr = {
		AF_UNIX,
		"sock",
	};
	struct addrinfo info = {
		.ai_family = AF_UNIX,
		.ai_socktype = SOCK_STREAM,
		.ai_protocol = 0,
		.ai_addr = (struct sockaddr *)&unaddr,
		.ai_addrlen = sizeof(unaddr),
	};
	struct addrinfo *addrinfo = &info;
	*/
	struct addrinfo *addrinfo;
	res = getaddrinfo(host, port, &hints, &addrinfo);
	if (res != 0)
		die("%s:%s: getaddrinfo: %s", host, port, gai_strerror(res));
	addrlen = addrinfo->ai_addrlen;
	memcpy(&addr, addrinfo->ai_addr, addrlen);
	freeaddrinfo(addrinfo);

	clients = calloc(nclients, sizeof(*clients));
	if (!clients)
		die("failed to allocate memory for connections");
	pollfds = calloc(nclients, sizeof(*pollfds));
	if (!clients)
		die("failed to allocate memory for connections");

	for (int i = 0; i < nclients; ++i)
		pollfds[i].fd = -1;

	now = gettime();

	cur_stat = now;
	cur_wakeup = now;
	cur_tick = now;
	tick_lag_last_update = now;

	while (true) {
		for (int i = 0; i < nclients; ++i) {
			poll_client(i);
		}

		if (cur_stat < now) {
			report_stats();
			cur_stat += stat_interval;
			if (cur_stat < now)
				cur_stat = now;
		}

		now = gettime();

		if (cur_wakeup < now) {
			// TODO: this turned out quite convoluted, and still doesn't do
			// excactly what it should. if the tick rate target cannot be
			// met, wakeups become progressively less frequent, eventually
			// clumping multiple whole ticks onto one wakeup, until the
			// catchup limit is reached, at which point the cycle starts
			// again. i hard capped the amount of work per wakeup to one
			// tick interval to prevent the clumping, but the weird cyclic
			// behavior remains.
			//
			// of course, the reason we're trying to vary the amount of
			// work per wakeup in the first place has to do with overhead
			// from other parts of the event loop, not the ticking itself.
			// does even that make sense, though? if ingesting a certain
			// amount of os events takes a certain amount of time
			// regardless, would this adjustment simply cause event
			// handling to fall behind? but treating the wakeup interval as
			// a hard requirement that must be met doesn't seem right
			// either.
			//
			// comment from the future: the above was written in
			// the context of an event loop that used epoll; poll()
			// as used here may be quite different in this respect.
			i64 actual_wakeup_time = now;
			bool first = true;
			for (;; first = false) {
				i64 target = actual_wakeup_time + wakeup_interval;
				if (target > cur_wakeup + tick_interval)
					target = cur_wakeup + tick_interval;
				if (target < cur_tick)
					break;
				target -= cur_tick;
				target = target * nclients / tick_interval;
				if (target == (i64)clients_ticked && first)
					++target;
				if (target <= (i64)clients_ticked)
					break;
				if (target > (i64)nclients)
					target = nclients;
				tick_clients(clients_ticked, target);
				now = gettime();
				clients_ticked = target;
				if (clients_ticked < nclients)
					break;
				clients_ticked = 0;
				cur_tick += tick_interval;
				if (cur_tick < now) {
					tick_lag_duration += now - tick_lag_last_update;
					if (cur_tick + tick_catchup_limit < now) {
						tick_lag += now - cur_tick;
						cur_tick = now;
					}
				} else {
					if (tick_lag == 0)
						tick_lag_duration = 0;
				}
				tick_lag_last_update = now;
			}
			i64 next_wakeup = cur_tick + clients_ticked * tick_interval / nclients;
			cur_wakeup = next_wakeup > cur_wakeup + wakeup_interval
				? next_wakeup
				: cur_wakeup + wakeup_interval;
		}

		i64 timeout = cur_wakeup - now;
		if (timeout < 0)
			timeout = 0;
		int timeout_ms = (timeout - 1) / 1000000 + 1;

		if (poll(pollfds, nclients, timeout_ms) < 0)
			dieerror("poll");

		now = gettime();
	}
}