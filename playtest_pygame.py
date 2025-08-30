
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, json, math, time, random, hashlib
from dataclasses import dataclass
from typing import Dict, Tuple, Optional, List

# --- Engine imports ---
sys.path.append(os.path.dirname(__file__))
from engine.worldgen_core.world.world_generator import WorldGenerator
from engine.worldgen_core.base.preset import Preset
from engine.worldgen_core.base.constants import KIND_GROUND, KIND_OBSTACLE, KIND_WATER, KIND_ROAD, DEFAULT_PALETTE
from engine.worldgen_core.utils.rle import decode_rle_rows, encode_rle_rows

# --- Optional PIL for saving thumbnails ---
try:
    from PIL import Image
    PIL_OK = True
except Exception:
    PIL_OK = False

# --- Pygame ---
try:
    import pygame
except Exception as e:
    print("Pygame не установлен. Установите: pip install pygame --prefer-binary")
    raise

# ---------------- CONFIG ----------------
CHUNK_SIZE = 128                 # тайлов в чанке
TILE_PX    = 4                   # размер тайла в пикселях (мастер-окно)
VIEW_TILES_W = 160               # ширина области видимости в тайлах (можно 150)
VIEW_TILES_H = 160               # высота области видимости в тайлах

MINIMAP_GRID = 5                 # 5x5 чанков
MINIMAP_TILE = 2                 # пикселей на тайл в миникарте (при склейке превью)

WORLD_ROOT = os.path.join(os.path.dirname(__file__), "world")
CITY_PATH = os.path.join(WORLD_ROOT, "city", "static", "0_0")
PRESET_PATH = os.path.join(os.path.dirname(__file__), "engine", "presets", "world", "base_default.json")

# ---------------- HELPERS ----------------
def hex_to_rgb(s: str) -> Tuple[int,int,int]:
    s = s.lstrip("#")
    if len(s)==8: s = s[2:]  # отбрасываем альфу если #AARRGGBB
    return int(s[0:2],16), int(s[2:4],16), int(s[4:6],16)

def derive_branch_seed(global_seed: int, side: str) -> int:
    h = hashlib.sha256(f"{global_seed}:{side}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "little", signed=False)

# ---------------- STORAGE ----------------
@dataclass
class Chunk:
    cx: int
    cz: int
    kind: List[List[str]]
    height: Optional[List[List[float]]] = None

class WorldStore:
    def __init__(self, preset: Preset, branch_side: Optional[str]=None, branch_seed: Optional[int]=None):
        self.preset = preset
        self.branch_side = branch_side  # 'E' or 'W' or None (в городе)
        self.branch_seed = branch_seed
        self.cache: Dict[Tuple[int,int,str], Chunk] = {}  # key = (cx,cz,world_id)

    # --- Paths ---
    def _branch_dir(self) -> Optional[str]:
        if not self.branch_side or self.branch_seed is None:
            return None
        return os.path.join(WORLD_ROOT, "branch", self.branch_side, str(self.branch_seed))

    def path_city_chunk(self, cx:int, cz:int) -> str:
        return os.path.join(CITY_PATH, f"{cx}_{cz}")

    def path_branch_chunk(self, cx:int, cz:int) -> Optional[str]:
        base = self._branch_dir()
        if not base: return None
        return os.path.join(base, f"{cx}_{cz}")

    # --- IO ---
    def _read_chunk_from_disk(self, world_id: str, cx:int, cz:int) -> Optional[Chunk]:
        if world_id == "city":
            dirp = self.path_city_chunk(cx, cz)
        else:
            dirp = self.path_branch_chunk(cx, cz)
        if not dirp: return None
        meta_path = os.path.join(dirp, "chunk.meta.json")
        rle_path  = os.path.join(dirp, "chunk.rle.json")
        if not (os.path.exists(meta_path) and os.path.exists(rle_path)):
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            with open(rle_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            rows = payload.get("rows") if isinstance(payload, dict) else payload
            grid_ids = decode_rle_rows(rows)
            # Преобразуем ID -> name через палитру из presets: 0=ground,1=obstacle,2=water,3=road,4=void
            ID2NAME = {0:"ground",1:"obstacle",2:"water",3:"road",4:"void"}
            kind = [[ID2NAME.get(v,"ground") for v in line] for line in grid_ids]
            return Chunk(cx=cx, cz=cz, kind=kind, height=None)
        except Exception as e:
            print("Ошибка чтения чанка:", dirp, e)
            return None

    def _ensure_dir(self, path: str):
        os.makedirs(path, exist_ok=True)

    def _save_chunk(self, world_id: str, cx:int, cz:int, kind: List[List[str]]):
        # сохраняем rle + meta + превью
        if world_id == "city":
            dirp = self.path_city_chunk(cx, cz)
        else:
            dirp = self.path_branch_chunk(cx, cz)
        if not dirp: return
        self._ensure_dir(dirp)

        # kind -> ID grid
        NAME2ID = {"ground":0,"obstacle":1,"water":2,"road":3,"void":4}
        grid_ids = [[NAME2ID.get(v,0) for v in row] for row in kind]
        rle = {"encoding":"rle_rows_v1","w":CHUNK_SIZE,"h":CHUNK_SIZE,"cx":cx,"cz":cz,"rows": encode_rle_rows(grid_ids)["rows"]}
        with open(os.path.join(dirp,"chunk.rle.json"),"w",encoding="utf-8") as f:
            json.dump(rle, f, ensure_ascii=False, indent=2)

        meta = {
            "version":"1.0", "type":"chunk_meta",
            "seed": int(self.branch_seed or 0), "size": CHUNK_SIZE, "cx": cx, "cz": cz,
            "world_id": "city" if world_id=="city" else f"branch/{self.branch_side}/{self.branch_seed}",
            "ports": {"N":[],"S":[],"W":[],"E":[]}, "edges":{}, "metrics":{}
        }
        with open(os.path.join(dirp,"chunk.meta.json"),"w",encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # preview
        if PIL_OK:
            pal = self.preset.export.get("palette", {})
            px_ground = hex_to_rgb(pal.get("ground", DEFAULT_PALETTE["ground"]))
            px_obst   = hex_to_rgb(pal.get("obstacle", DEFAULT_PALETTE["obstacle"]))
            px_water  = hex_to_rgb(pal.get("water", DEFAULT_PALETTE["water"]))
            px_road   = hex_to_rgb(pal.get("road", "#d2b48c"))
            im = Image.new("RGB", (CHUNK_SIZE, CHUNK_SIZE))
            pix = im.load()
            for z in range(CHUNK_SIZE):
                for x in range(CHUNK_SIZE):
                    k = kind[z][x]
                    if k=="ground": pix[x,z]=px_ground
                    elif k=="obstacle": pix[x,z]=px_obst
                    elif k=="water": pix[x,z]=px_water
                    elif k=="road": pix[x,z]=px_road
                    else: pix[x,z]=(0,0,0)
            im.save(os.path.join(dirp, "preview.png"), "PNG")

    def _generate_chunk(self, world_id: str, cx:int, cz:int) -> Chunk:
        # Простая генерация через WorldGenerator (детерминированно по branch_seed и координатам)
        gen = WorldGenerator(Preset.load(PRESET_PATH))
        params = {"seed": int(self.branch_seed or 0), "cx": cx, "cz": cz}
        res = gen.generate(params)
        kind = res.layers["kind"]
        self._save_chunk(world_id, cx, cz, kind)
        return Chunk(cx=cx, cz=cz, kind=kind)

    def get_chunk(self, world_id: str, cx:int, cz:int) -> Chunk:
        key = (cx, cz, world_id)
        if key in self.cache:
            return self.cache[key]
        ch = self._read_chunk_from_disk(world_id, cx, cz)
        if ch is None:
            ch = self._generate_chunk(world_id, cx, cz)
        self.cache[key] = ch
        return ch

# ---------------- GAME STATE ----------------
@dataclass
class Player:
    wx: int  # world tile X
    wz: int  # world tile Z

class Game:
    def __init__(self, seed: int):
        self.global_seed = int(seed)
        self.preset = Preset.load(PRESET_PATH)
        self.palette = self.preset.export.get("palette", {})
        self.store = WorldStore(self.preset, None, None)  # в городе
        self.world_id = "city"
        self.center_c = (0, 0)  # текущий центральный чанк (cx,cz) для города/ветки
        # старт в центре города
        self.player = Player(wx=CHUNK_SIZE//2, wz=CHUNK_SIZE//2)

        # Если игрок пересёк границу города -> фиксируем ветку
        self.branch_side: Optional[str] = None  # 'E'/'W'
        self.branch_seed: Optional[int] = None

        # Параметры экрана
        self.screen_w = VIEW_TILES_W * TILE_PX + MINIMAP_GRID*CHUNK_SIZE//4  # место для миникарты
        self.screen_h = VIEW_TILES_H * TILE_PX

        # Путь
        self.path: List[Tuple[int,int]] = []  # последовательность world-тайлов

    # --- Branch logic ---
    def _enter_branch_if_needed(self):
        cx, cz = self.center_c
        px, pz = self.player.wx - cx*CHUNK_SIZE, self.player.wz - cz*CHUNK_SIZE
        # Выходы из города по краю: E/W
        if self.branch_side is None and self.world_id=="city":
            if px < 0:
                # Запрещаем уход на W до захода в город (искусственно возвращаем)
                self.player.wx = 0
            elif px >= CHUNK_SIZE:
                # Вход в ветку E
                self.branch_side = "E"
                # пытаемся обнаружить существующую ветку: берем любую первую папку
                branch_root = os.path.join(WORLD_ROOT, "branch", self.branch_side)
                os.makedirs(branch_root, exist_ok=True)
                # если уже есть подпапка-Seed -> используем её; иначе derive
                seeds = [d for d in os.listdir(branch_root) if d.isdigit()]
                if seeds:
                    self.branch_seed = int(sorted(seeds)[0])
                else:
                    self.branch_seed = derive_branch_seed(self.global_seed, self.branch_side)
                self.store.branch_side = self.branch_side
                self.store.branch_seed = self.branch_seed
                self.world_id = "branch"
                # перенос на (1,0), корректируем мировые координаты
                self.center_c = (1, 0)
                self.player.wx = self.center_c[0]*CHUNK_SIZE + 0
                self.player.wz = self.center_c[1]*CHUNK_SIZE + pz
            elif px < 0 or pz < 0 or pz >= CHUNK_SIZE:
                # остальные края города сейчас не используем
                pass
        else:
            # Ветка E: запрещаем cx<0, кроме перехода (1,0)->(0,0)
            if self.branch_side=="E":
                # если пытаемся уйти в cx<0, возвращаем на границу
                if (self.player.wx // CHUNK_SIZE) < 0:
                    # Разрешаем только если текущий чанк (1,0) -> (0,0)
                    if (self.player.wx // CHUNK_SIZE, self.player.wz // CHUNK_SIZE) == (0,0):
                        pass
                    else:
                        self.player.wx = 0

    # --- Loading 3x3 around center ---
    def _preload_around_center(self):
        cx0, cz0 = self.player.wx // CHUNK_SIZE, self.player.wz // CHUNK_SIZE
        if (cx0, cz0) != self.center_c:
            self.center_c = (cx0, cz0)
        for dz in (-1,0,1):
            for dx in (-1,0,1):
                c = (cx0+dx, cz0+dz)
                self.store.get_chunk(self.world_id, c[0], c[1])

    # --- Rendering ---
    def _get_color(self, kind: str) -> Tuple[int,int,int]:
        pal = self.palette
        if kind=="ground": return hex_to_rgb(pal.get("ground", DEFAULT_PALETTE["ground"]))
        if kind=="obstacle": return hex_to_rgb(pal.get("obstacle", DEFAULT_PALETTE["obstacle"]))
        if kind=="water": return hex_to_rgb(pal.get("water", DEFAULT_PALETTE["water"]))
        if kind=="road": return hex_to_rgb(pal.get("road", "#d2b48c"))
        return (0,0,0)

    def render(self, screen):
        # левый блок — локальный вид
        left_w = VIEW_TILES_W * TILE_PX
        pygame.draw.rect(screen, (10,10,10), (0,0,left_w,self.screen_h))

        # вычислим левый-верхний world-тайл так, чтобы игрок был в центре
        wx0 = self.player.wx - VIEW_TILES_W//2
        wz0 = self.player.wz - VIEW_TILES_H//2

        # перебор тайлов, обращаясь к чанкам по мере необходимости
        for vy in range(VIEW_TILES_H):
            wz = wz0 + vy
            cz = wz // CHUNK_SIZE
            lz = wz - cz*CHUNK_SIZE
            for vx in range(VIEW_TILES_W):
                wx = wx0 + vx
                cx = wx // CHUNK_SIZE
                lx = wx - cx*CHUNK_SIZE
                ch = self.store.get_chunk(self.world_id, cx, cz)
                k = ch.kind[lz][lx] if 0<=lx<CHUNK_SIZE and 0<=lz<CHUNK_SIZE else "obstacle"
                color = self._get_color(k)
                pygame.draw.rect(screen, color, (vx*TILE_PX, vy*TILE_PX, TILE_PX, TILE_PX))

        # игрок
        px = (self.player.wx - wx0)*TILE_PX
        pz = (self.player.wz - wz0)*TILE_PX
        pygame.draw.rect(screen, (255,255,255), (px, pz, TILE_PX, TILE_PX))

        # правый блок — миникарта 5x5
        mm_left = left_w + 8
        mm_tile = CHUNK_SIZE // 4  # в пикселях
        for j in range(-MINIMAP_GRID//2, MINIMAP_GRID//2+1):
            for i in range(-MINIMAP_GRID//2, MINIMAP_GRID//2+1):
                cx = self.player.wx // CHUNK_SIZE + i
                cz = self.player.wz // CHUNK_SIZE + j
                # ищем preview.png
                if self.world_id=="city":
                    dirp = os.path.join(CITY_PATH, f"{cx}_{cz}")
                else:
                    dirp = self.store.path_branch_chunk(cx, cz) or ""
                prev = os.path.join(dirp, "preview.png")
                rect = (mm_left + (i+MINIMAP_GRID//2)*mm_tile,
                        8 + (j+MINIMAP_GRID//2)*mm_tile, mm_tile, mm_tile)
                if os.path.exists(prev):
                    try:
                        surf = pygame.image.load(prev)
                        surf = pygame.transform.scale(surf, (mm_tile, mm_tile))
                        screen.blit(surf, rect[:2])
                    except Exception:
                        pygame.draw.rect(screen, (30,30,30), rect)
                else:
                    # если чанка нет — пустышка
                    pygame.draw.rect(screen, (30,30,30), rect, 1)

        # текстовая инфа
        font = pygame.font.SysFont("consolas", 14)
        info = f"seed={self.global_seed} world={'city' if self.world_id=='city' else self.branch_side+':'+str(self.branch_seed)} pos=({self.player.wx},{self.player.wz}) c={self.center_c}"
        txt = font.render(info, True, (230,230,230))
        screen.blit(txt, (8, self.screen_h-20))

    # --- Input ---
    def click_to(self, mx: int, my: int):
        # переводим в world-координаты
        left_w = VIEW_TILES_W * TILE_PX
        if mx >= left_w: 
            return  # клики по миникарте игнорим в MVP
        wx0 = self.player.wx - VIEW_TILES_W//2
        wz0 = self.player.wz - VIEW_TILES_H//2
        gx = wx0 + mx//TILE_PX
        gz = wz0 + my//TILE_PX
        # простейший прямолинейный путь с шагами по 4-связности
        self.path = self._greedy_path((self.player.wx, self.player.wz), (gx, gz))

    def _greedy_path(self, start: Tuple[int,int], goal: Tuple[int,int]) -> List[Tuple[int,int]]:
        # Не A*: минимальный прототип — идём по Манхэттену, избегая препятствий (перестраиваясь)
        sx, sz = start; gx, gz = goal
        path: List[Tuple[int,int]] = []
        x, z = sx, sz
        cap = 20000
        while (x,z)!=(gx,gz) and cap>0:
            cap -= 1
            dx = 1 if gx>x else (-1 if gx<x else 0)
            dz = 1 if gz>z else (-1 if gz<z else 0)
            cand = [(x+dx, z), (x, z+dz), (x+dx, z+dz), (x, z)]
            moved=False
            for nx, nz in cand:
                cx, cz = nx//CHUNK_SIZE, nz//CHUNK_SIZE
                lx, lz = nx - cx*CHUNK_SIZE, nz - cz*CHUNK_SIZE
                ch = self.store.get_chunk(self.world_id, cx, cz)
                if 0<=lx<CHUNK_SIZE and 0<=lz<CHUNK_SIZE and ch.kind[lz][lx] != "obstacle" and ch.kind[lz][lx]!="water":
                    x, z = nx, nz
                    path.append((x,z))
                    moved=True
                    break
            if not moved:
                break
        return path

    def step(self):
        # движение по пути, 1 тайл за тик
        if self.path:
            self.player.wx, self.player.wz = self.path.pop(0)
        self._enter_branch_if_needed()
        self._preload_around_center()

# ---------------- MENU ----------------
def menu_get_seed(screen) -> int:
    font = pygame.font.SysFont("consolas", 24)
    seed_str = ""
    hint = "Введите seed и нажмите Enter"
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    if seed_str.strip() == "":
                        return 0
                    try:
                        return int(seed_str)
                    except:
                        # строковый сид -> хеш
                        h = hashlib.sha256(seed_str.encode("utf-8")).digest()
                        return int.from_bytes(h[:8], "little")
                elif event.key == pygame.K_BACKSPACE:
                    seed_str = seed_str[:-1]
                else:
                    if event.unicode and (event.unicode.isalnum() or event.unicode in (" ", "_", "-")):
                        seed_str += event.unicode
        screen.fill((16,16,28))
        t1 = font.render(hint, True, (230,230,230))
        t2 = font.render(seed_str, True, (160,220,160))
        screen.blit(t1, (40, 80))
        screen.blit(t2, (40, 120))
        pygame.display.flip()

# ---------------- MAIN ----------------
def main():
    pygame.init()
    # Окно суммарной ширины (игровая панель + миникарта)
    screen_w = VIEW_TILES_W*TILE_PX + CHUNK_SIZE//4*MINIMAP_GRID + 16
    screen_h = VIEW_TILES_H*TILE_PX
    screen = pygame.display.set_mode((screen_w, screen_h))
    pygame.display.set_caption("Worldgen Tester (Pygame)")

    seed = menu_get_seed(screen)
    game = Game(seed)

    clock = pygame.time.Clock()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit(0)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button==1:
                mx, my = event.pos
                game.click_to(mx, my)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit(0)
                # WASD ручные шаги
                if event.key in (pygame.K_w, pygame.K_a, pygame.K_s, pygame.K_d):
                    dx = (event.key==pygame.K_d) - (event.key==pygame.K_a)
                    dz = (event.key==pygame.K_s) - (event.key==pygame.K_w)
                    game.path = [(game.player.wx+dx, game.player.wz+dz)]

        game.step()
        game.render(screen)
        pygame.display.flip()
        clock.tick(30)

if __name__=="__main__":
    main()
