import numpy as np
import glfw
from OpenGL.GL import *
import OpenGL.GL.shaders as shaders
import math
import sys
import ctypes
import pygame
from pygame import freetype

# -------------------------- Janela -------------------------- #
WINDOW_WIDTH  = 800
WINDOW_HEIGHT = 600

# --------------------------- Cores -------------------------- #
BRANCO   = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
PRETO    = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
VERDE    = np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32)   # Aplicação
AZUL     = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float32)   # Transporte
AMARELO  = np.array([1.0, 1.0, 0.0, 1.0], dtype=np.float32)   # Rede
VERMELHO = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float32)   # Enlace
MAGENTA  = np.array([1.0, 0.0, 1.0, 1.0], dtype=np.float32)   # Física

# cores da pilha (de baixo p/ cima: Física → Aplicação)
LAYERS_COLORS = [MAGENTA, VERMELHO, AMARELO, AZUL, VERDE]

# ------------------- Estados da animação -------------------- #
ESTADOS = {
    "IDLE"        : 0,  # parado
    # Encapsulamento (PC esquerdo)
    "APLICACAO"   : 1,
    "TRANSPORTE"  : 2,
    "REDE"        : 3,
    "ENLACE"      : 4,
    "FISICA"      : 5,
    # Movimento e captura de camadas
    "MOVE"        : 6,
    # Desencapsulamento (PC direito)
    "DFISICA"     : 7,
    "DENLACE"     : 8,
    "DREDE"       : 9,
    "DTRANSPORTE" : 10,
    "DONE"        : 11  # fim → volta para IDLE
}

# ---------------- Variáveis globais ---------------- #
current_msg = ""
estadoAtual        = ESTADOS["IDLE"]
progressoAnimacao  = 0.0
velocidadeAnimacao = 0.002

# configurações de camadas
altura_faixa = 20
gap          = 2
# posições verticais das 5 camadas (0=Física,...,4=Aplicação)
y_positions = [300 + (-50 + i*(altura_faixa + gap)) for i in range(5)]

# posição inicial (ao lado do retângulo verde Aplicação)
mensagem_start_x = 150 + 30 + 40
mensagem_x       = mensagem_start_x
mensagem_y       = y_positions[4]

# destino horizontal (ao lado do PC direito)
destino_x = 650 - (30 + 40)

# waypoints: (x,y,color) para captura de camadas, depois atravessar e soltar
waypoints = [
    # ---------- DESCIDA  (PC esquerdo) ----------
    (mensagem_start_x, y_positions[4], VERDE   ,"Camada de Aplicação: dados da aplicação"),
    (mensagem_start_x, y_positions[3], AZUL    , "Camada Transporte: cabeçalho TCP/UDP"),
    (mensagem_start_x, y_positions[2], AMARELO , "Camada Rede: cabeçalho IP"),
    (mensagem_start_x, y_positions[1], VERMELHO, "Camada Enlace: cabeçalho Ethernet"),
    (mensagem_start_x, y_positions[0], MAGENTA , "Camada Física: sinais elétricos"),

    # ---------- TRAVESSIA ----------
    (destino_x       , y_positions[0], None    , "Enviando pela rede…"),

    # ---------- SUBIDA  (PC direito) ----------
    (destino_x       , y_positions[1], None , "Desencaps. Enlace: remove Ethernet"),
    (destino_x       , y_positions[2], None , "Desencaps. Rede : remove IP"),
    (destino_x       , y_positions[3], None , "Desencaps. Transp: remove TCP"),
    (destino_x       , y_positions[4], None , "Aplicação destino: mensagem recebida!")
]

waypoint_idx = 0
# lista de cores adquiridas, iniciando com Aplicação (verde)
acquired_colors = [VERDE]
# track origem do segmento atual
segment_start_x = mensagem_x
segment_start_y = mensagem_y

# ----------------- Shaders GLSL ----------------- #
color_vertex_shader = """
#version 330 core
layout (location = 0) in vec2 position;
uniform mat4 model;
uniform mat4 projection;
void main() {
    gl_Position = projection * model * vec4(position, 0.0, 1.0);
}
"""

color_fragment_shader = """
#version 330 core
out vec4 fragColor;
uniform vec4 color;
void main() {
    fragColor = color;
}
"""

text_vertex_shader = """
#version 330 core
layout (location = 0) in vec2 position;
layout (location = 1) in vec2 texCoord;
uniform mat4 model;
uniform mat4 projection;
out vec2 TexCoord;
void main() {
    gl_Position = projection * model * vec4(position, 0.0, 1.0);
    TexCoord = texCoord;
}
"""

text_fragment_shader = """
#version 330 core
in vec2 TexCoord;
out vec4 fragColor;
uniform sampler2D text;
uniform vec4 color;
void main() {
    vec4 sampled = texture(text, TexCoord);
    fragColor = vec4(color.rgb, 1.0) * sampled;
}
"""

# ============================================================ #
#                           Renderer                           #
# ============================================================ #
class Renderer:
    def __init__(self):
        self.color_shader = None
        self.text_shader  = None
        self.quad_vao     = None
        self.hexagon_vao  = None
        self.projection   = None

    def init_shaders(self):
        self.color_shader = shaders.compileProgram(
            shaders.compileShader(color_vertex_shader, GL_VERTEX_SHADER),
            shaders.compileShader(color_fragment_shader, GL_FRAGMENT_SHADER)
        )
        self.text_shader = shaders.compileProgram(
            shaders.compileShader(text_vertex_shader, GL_VERTEX_SHADER),
            shaders.compileShader(text_fragment_shader, GL_FRAGMENT_SHADER)
        )
        self.projection = self._ortho(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
        glUseProgram(self.color_shader)
        glUniformMatrix4fv(glGetUniformLocation(self.color_shader, "projection"), 1, GL_FALSE, self.projection)
        glUseProgram(self.text_shader)
        glUniformMatrix4fv(glGetUniformLocation(self.text_shader, "projection"), 1, GL_FALSE, self.projection)

    def init_buffers(self):
        # Quad
        self.quad_vao = glGenVertexArrays(1)
        quad_vbo = glGenBuffers(1)
        quad_vertices = np.array([-0.5, -0.5,
                                   0.5, -0.5,
                                   0.5,  0.5,
                                  -0.5,  0.5], dtype=np.float32)
        quad_idx = np.array([0,1,2, 0,2,3], dtype=np.uint32)
        glBindVertexArray(self.quad_vao)
        glBindBuffer(GL_ARRAY_BUFFER, quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_vertices.nbytes, quad_vertices, GL_STATIC_DRAW)
        ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, quad_idx.nbytes, quad_idx, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        # Hexágono
        self.hexagon_vao = glGenVertexArrays(1)
        hex_vbo = glGenBuffers(1)
        vertices = [0.0, 0.0]
        indices = []
        for i in range(6):
            ang = math.radians(60 * i)
            vertices += [math.cos(ang), math.sin(ang)]
            if i < 5:
                indices += [0, i+1, i+2]
            else:
                indices += [0, i+1, 1]
        vertices = np.array(vertices, dtype=np.float32)
        indices  = np.array(indices,  dtype=np.uint32)
        glBindVertexArray(self.hexagon_vao)
        glBindBuffer(GL_ARRAY_BUFFER, hex_vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STATIC_DRAW)
        ebo2 = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo2)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    def _ortho(self, l, r, b, t):
        w, h = r-l, t-b
        m = np.identity(4, dtype=np.float32)
        m[0,0] = 2.0/w
        m[1,1] = 2.0/h
        m[3,0] = -(r+l)/w
        m[3,1] = -(t+b)/h
        m[2,2] = -1.0
        return m

    def _draw(self, vao, count, x, y, sx, sy, cor):
        glUseProgram(self.color_shader)
        model = np.identity(4, dtype=np.float32)
        model[0,0] = sx
        model[1,1] = sy
        model[3,0] = x
        model[3,1] = y
        glUniformMatrix4fv(glGetUniformLocation(self.color_shader, "model"), 1, GL_FALSE, model)
        glUniform4fv(glGetUniformLocation(self.color_shader, "color"), 1, cor)
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    # desenho de retângulo
    def desenha_quad(self, x, y, w, h, cor):
        self._draw(self.quad_vao, 6, x, y, w, h, cor)

        # desenho de hexágono com bordas concêntricas de cores adquiridas
        # desenho de hexágono com bordas concêntricas de cores adquiridas
        # desenho de hexágono com bordas concêntricas de cores adquiridas
    def desenha_mensagem(self, x, y, cores, rot=0.0, scale=0.7):
        """
        Desenha hexágono central menor e anéis concêntricos em torno, correspondendo às cores adquiridas.
        Anéis não adquiridos permanecem transparentes.
        """
        base = 30 * scale
        step = 8 * scale
        # ordem fixa de anéis: Aplicação (verde), Transporte (azul), Rede (amarelo), Enlace (vermelho), Física (magenta)
        ring_order = [VERDE, AZUL, AMARELO, VERMELHO, MAGENTA]
        # desenhar maiores primeiro para que fiquem atrás
        for idx in range(len(ring_order)-1, -1, -1):
            layer_color = ring_order[idx]
            tamanho = base + idx * step
            
            # verifica aquisição comparando arrays
            acquired = any(np.array_equal(layer_color, c) for c in cores)
            if acquired:
                cor = layer_color
            else:
                cor = np.array([layer_color[0], layer_color[1], layer_color[2], 0.0], dtype=np.float32)
            self._draw(self.hexagon_vao, 18, x, y, tamanho, tamanho, cor)

    def desenha_pc(self, x, y, scale=1.0, ativo=False):
        """
        Monitor + 5 faixas horizontais coloridas (camadas).
        x,y: base do monitor (mesmo ponto usado antes).
        """
        # --------- monitor ----------
        self.desenha_quad(x, y + 90*scale, 120*scale, 60*scale,
                          np.array([0.2,0.2,0.2,1.0]))
        cor_tela = np.array([0.8,1.0,0.8,1.0]) if ativo else \
                   np.array([0.1,0.1,0.1,1.0])
        self.desenha_quad(x, y + 90*scale, 100*scale, 40*scale, cor_tela)

        # --------- pilha de 5 camadas ----------
        largura      = 60 * scale
        alt_faixa    = altura_faixa * scale
        gap_s        = gap * scale
        for i, cor in enumerate(LAYERS_COLORS):      # Física=0 … Aplicação=4
            cx = x
            cy = -50 + y + i*(alt_faixa + gap_s)
            self.desenha_quad(cx, cy, largura, alt_faixa, cor)

    # texto (igual antes)
    def escreve_texto(self, x, y, texto, cor=(0,0,0)):
        from PIL import Image, ImageDraw, ImageFont
        font = ImageFont.truetype("arial.ttf", 24)
        bbox = font.getbbox(texto)
        img = Image.new("RGBA", (bbox[2], bbox[3]), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.text((0,0), texto, font=font, fill=(int(cor[0]*255), int(cor[1]*255), int(cor[2]*255), 255))
        data = img.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, img.width, img.height, 0, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        quad = np.array([x, y, x+img.width, y, x+img.width, y+img.height, x, y+img.height], dtype=np.float32)
        uv   = np.array([0,0, 1,0, 1,1, 0,1], dtype=np.float32)
        vao  = glGenVertexArrays(1)
        vbo  = glGenBuffers(2)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo[0])
        glBufferData(GL_ARRAY_BUFFER, quad.nbytes, quad, GL_STATIC_DRAW)
        glVertexAttribPointer(0,2,GL_FLOAT,GL_FALSE,0,ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, vbo[1])
        glBufferData(GL_ARRAY_BUFFER, uv.nbytes, uv, GL_STATIC_DRAW)
        glVertexAttribPointer(1,2,GL_FLOAT,GL_FALSE,0,ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glUseProgram(self.text_shader)
        model = np.identity(4, dtype=np.float32)
        glUniformMatrix4fv(glGetUniformLocation(self.text_shader, "model"), 1, GL_FALSE, model)
        glUniform4fv(glGetUniformLocation(self.text_shader, "color"), 1, np.append(cor, 1))
        glUniform1i(glGetUniformLocation(self.text_shader, "text"), 0)
        glActiveTexture(GL_TEXTURE0); glBindTexture(GL_TEXTURE_2D, texture)
        glBindVertexArray(vao); glDrawArrays(GL_TRIANGLE_FAN, 0, 4)
        glDeleteVertexArrays(1, [vao]); glDeleteBuffers(2, vbo); glDeleteTextures([texture])

# ============================================================ #
#                         Aplicação                           #
# ============================================================ #
class Application:
    def __init__(self): self.renderer=None

    def init(self):
        if not glfw.init(): return False
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR,3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR,3)
        glfw.window_hint(glfw.OPENGL_PROFILE,glfw.OPENGL_CORE_PROFILE)
        self.window = glfw.create_window(WINDOW_WIDTH, WINDOW_HEIGHT, "Encapsulamento", None, None)
        if not self.window:
            glfw.terminate(); return False
        glfw.make_context_current(self.window)
        glfw.set_key_callback(self.window, self.key_callback)
        glViewport(0,0,WINDOW_WIDTH,WINDOW_HEIGHT)
        glClearColor(*BRANCO)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA,GL_ONE_MINUS_SRC_ALPHA)

        self.renderer = Renderer()
        self.renderer.init_shaders()
        self.renderer.init_buffers()
        return True

    # ---------------- Loop principal ---------------- #
    def run(self):
        print("ESPAÇO = iniciar | R = reset | ESC = sair")
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            self.update()
            self.render()
            glfw.swap_buffers(self.window)
        glfw.terminate()

    # ------------- Atualiza lógica/estados ----------- #
    def update(self):
        global estadoAtual, progressoAnimacao
        global mensagem_x, mensagem_y, waypoint_idx, segment_start_x, segment_start_y, acquired_colors, current_msg

        if ESTADOS["APLICACAO"] <= estadoAtual <= ESTADOS["FISICA"]:
            progressoAnimacao += velocidadeAnimacao
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0
                estadoAtual += 1
                if estadoAtual == ESTADOS["MOVE"]:
                    segment_start_x = mensagem_x
                    segment_start_y = mensagem_y

        elif estadoAtual == ESTADOS["MOVE"]:
        # ---------------- MOVIMENTAÇÃO ENTRE WAYPOINTS ---------------- #
            if waypoint_idx < len(waypoints):
                tx, ty, color, msg = waypoints[waypoint_idx]     # destino atual
                progressoAnimacao += velocidadeAnimacao
                mensagem_x = segment_start_x + (tx - segment_start_x) * progressoAnimacao
                mensagem_y = segment_start_y + (ty - segment_start_y) * progressoAnimacao

            # Chegou ao waypoint ------------------------------------------------
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0
                global current_msg
                current_msg = msg

                if color is not None:
                    # Descendo no PC esquerdo  →  GANHA camada (append)
                    acquired_colors.append(color)
                else:
                    # Subindo no PC direito   →  PERDE camada (pop)
                    if acquired_colors:
                        acquired_colors.pop()

                # Próximo segmento
                waypoint_idx += 1
                segment_start_x = mensagem_x
                segment_start_y = mensagem_y

                # Terminou todos os waypoints → começa desencapsulamento
                if waypoint_idx == len(waypoints):
                    estadoAtual = ESTADOS["DFISICA"]

        elif ESTADOS["DFISICA"] <= estadoAtual <= ESTADOS["DTRANSPORTE"]:
            progressoAnimacao += velocidadeAnimacao
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0

            # ---------- remove o anel mais externo ----------
            if acquired_colors:           # só se houver algo a tirar
                acquired_colors.pop()      # último da lista = borda externa
            # -------------------------------------------------

                estadoAtual += 1
                if estadoAtual == ESTADOS["DONE"]:
                    estadoAtual = ESTADOS["IDLE"]
                    mensagem_x = mensagem_start_x
                    mensagem_y = y_positions[4]
                    waypoint_idx = 0
                    acquired_colors = [VERDE]

    # ------------------ Desenha cena ------------------ #
    def render(self):
        glClear(GL_COLOR_BUFFER_BIT)

        ativo_esq = ESTADOS["APLICACAO"] <= estadoAtual <= ESTADOS["FISICA"]
        ativo_dir = estadoAtual != ESTADOS["IDLE"] and estadoAtual >= ESTADOS["MOVE"]

        self.renderer.desenha_pc(150, 300, 1.0, ativo_esq)
        self.renderer.desenha_pc(650, 300, 1.0, ativo_dir)

        if estadoAtual == ESTADOS["MOVE"]:
            self.renderer.desenha_mensagem(mensagem_x, mensagem_y, acquired_colors)
        if current_msg:
            self.renderer.escreve_texto(80, 550, current_msg)
        else:
            def cores_por_estado(st):
                if st in (ESTADOS["APLICACAO"], ESTADOS["DTRANSPORTE"]): return [VERDE]
                if st in (ESTADOS["TRANSPORTE"], ESTADOS["DREDE"]): return [AZUL, VERDE]
                if st in (ESTADOS["REDE"], ESTADOS["DENLACE"]): return [AMARELO, AZUL, VERDE]
                if st in (ESTADOS["ENLACE"], ESTADOS["DFISICA"]): return [VERMELHO, AMARELO, AZUL, VERDE]
                if st in (ESTADOS["FISICA"], ESTADOS["MOVE"]): return [MAGENTA, VERMELHO, AMARELO, AZUL, VERDE]
                return []

            if estadoAtual != ESTADOS["IDLE"]:
               self.renderer.desenha_mensagem(mensagem_x, mensagem_y, VERDE)
                # textos por estado (bloco original)
           
            elif estadoAtual == ESTADOS["IDLE"]:
                self.renderer.escreve_texto(200, 500, "Pressione ESPACO para iniciar a animacao")
                self.renderer.escreve_texto(150, 470, "Visualizacao do encapsulamento de pacotes")

    # ---------------- Callback de teclado ------------- #
    def key_callback(self, window, key, scancode, action, mods):
        global estadoAtual, progressoAnimacao, mensagem_x, mensagem_y, waypoint_idx, acquired_colors
        if action != glfw.PRESS: return
        if key == glfw.KEY_SPACE and estadoAtual == ESTADOS["IDLE"]:
            estadoAtual = ESTADOS["APLICACAO"]
            progressoAnimacao = 0.0
            mensagem_x = mensagem_start_x
            mensagem_y = y_positions[4]
            waypoint_idx = 0
            acquired_colors = [VERDE]
        elif key == glfw.KEY_R:
            estadoAtual = ESTADOS["IDLE"]
            progressoAnimacao = 0.0
            mensagem_x = mensagem_start_x
            mensagem_y = y_positions[4]
            waypoint_idx = 0
            acquired_colors = [VERDE]
        elif key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)

# ----------------------- Função main ----------------------- #
def main():
    app = Application()
    if app.init(): app.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
