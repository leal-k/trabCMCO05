import numpy as np
import glfw
from OpenGL.GL import *
import OpenGL.GL.shaders as shaders
import math
import sys
import ctypes

# -------------------------- Janela -------------------------- #
WINDOW_WIDTH  = 800
WINDOW_HEIGHT = 600

# --------------------------- Cores -------------------------- #
BRANCO  = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
PRETO   = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
VERMELHO= np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float32)
VERDE   = np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32)
AZUL    = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float32)
AMARELO = np.array([1.0, 1.0, 0.0, 1.0], dtype=np.float32)
CIANO   = np.array([0.0, 1.0, 1.0, 1.0], dtype=np.float32)  # não usado
MAGENTA = np.array([1.0, 0.0, 1.0, 1.0], dtype=np.float32)

# ------------------- Estados da animação -------------------- #
ESTADOS = {
    "IDLE"        : 0,  # parado
    # Encapsulamento (PC esquerdo)
    "APLICACAO"   : 1,
    "TRANSPORTE"  : 2,
    "REDE"        : 3,
    "ENLACE"      : 4,
    "FISICA"      : 5,
    # Movimento horizontal
    "MOVE"        : 6,
    # Desencapsulamento (PC direito)
    "DFISICA"     : 7,
    "DENLACE"     : 8,
    "DREDE"       : 9,
    "DTRANSPORTE" : 10,
    "DONE"        : 11  # fim → volta para IDLE
}

# ---------------- Variáveis globais ---------------- #
estadoAtual        = ESTADOS["IDLE"]     # estado inicial
progressoAnimacao  = 0.0                 # 0–1 dentro do estado
velocidadeAnimacao = 0.002               # quanto avança por frame
mensagem_x         = 150                 # posição x do “pacote”
mensagem_y         = 200                 # posição y fixo
destino_x          = 650                 # x sobre PC direito

# ----------------- Shaders GLSL ----------------- #
vertex_shader = """
#version 330 core
layout (location = 0) in vec2 position;
uniform mat4 model;
uniform mat4 projection;
void main()
{
    gl_Position = projection * model * vec4(position, 0.0, 1.0);
}
"""

fragment_shader = """
#version 330 core
out vec4 fragColor;
uniform vec4 color;
void main()
{
    fragColor = color;
}
"""

# ============================================================ #
#                           Renderer                           #
# ============================================================ #
class Renderer:
    def __init__(self):
        self.shader      = None
        self.quad_vao    = None
        self.hexagon_vao = None
        self.projection  = None

    # -------- Compilação de shaders e matriz de projeção ------ #
    def init_shaders(self):
        self.shader = shaders.compileProgram(
            shaders.compileShader(vertex_shader,   GL_VERTEX_SHADER),
            shaders.compileShader(fragment_shader, GL_FRAGMENT_SHADER)
        )
        self.projection = self._ortho(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
        glUseProgram(self.shader)
        glUniformMatrix4fv(
            glGetUniformLocation(self.shader, "projection"),
            1, GL_FALSE, self.projection
        )

    # ---------------- Criação de buffers ---------------- #
    def init_buffers(self):
        # ---- Quadrado ---- #
        self.quad_vao = glGenVertexArrays(1)
        quad_vbo      = glGenBuffers(1)

        quad_vertices = np.array([
            -0.5, -0.5,
             0.5, -0.5,
             0.5,  0.5,
            -0.5,  0.5
        ], dtype=np.float32)
        quad_idx = np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)

        glBindVertexArray(self.quad_vao)
        glBindBuffer(GL_ARRAY_BUFFER, quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_vertices.nbytes, quad_vertices, GL_STATIC_DRAW)

        ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, quad_idx.nbytes, quad_idx, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # ---- Hexágono (centro + 6 vértices) ---- #
        self.hexagon_vao = glGenVertexArrays(1)
        hex_vbo          = glGenBuffers(1)

        hex_vertices = [0.0, 0.0]  # centro
        hex_idx      = []
        for i in range(6):
            ang = math.radians(60*i)
            hex_vertices += [math.cos(ang), math.sin(ang)]
            # triângulos tipo “pizza”
            hex_idx += [0, i+1, i+2] if i < 5 else [0, i+1, 1]

        hex_vertices = np.array(hex_vertices, dtype=np.float32)
        hex_idx      = np.array(hex_idx, dtype=np.uint32)

        glBindVertexArray(self.hexagon_vao)
        glBindBuffer(GL_ARRAY_BUFFER, hex_vbo)
        glBufferData(GL_ARRAY_BUFFER, hex_vertices.nbytes, hex_vertices, GL_STATIC_DRAW)

        ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, hex_idx.nbytes, hex_idx, GL_STATIC_DRAW)

        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2*4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)  # limpa

    # -------- Matriz ortográfica (0…px) para 2D -------- #
    def _ortho(self, l, r, b, t):
        w, h = r-l, t-b
        ortho = np.identity(4, dtype=np.float32)
        ortho[0, 0] =  2.0 / w
        ortho[1, 1] =  2.0 / h
        ortho[3, 0] = -(r + l) / w
        ortho[3, 1] = -(t + b) / h
        ortho[2, 2] = -1.0
        return ortho

    # -------- Função genérica para desenhar shape -------- #
    def _draw(self, vao, count, x, y, sx, sy, cor):
        glUseProgram(self.shader)
        model = np.identity(4, dtype=np.float32)
        model[0, 0] = sx
        model[1, 1] = sy
        model[3, 0] = x
        model[3, 1] = y
        glUniformMatrix4fv(glGetUniformLocation(self.shader, "model"), 1, GL_FALSE, model)
        glUniform4fv(glGetUniformLocation(self.shader, "color"), 1, cor)
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    # ---- Envelopes de uso fácil ---- #
    def desenha_quad(self, x, y, w, h, cor):
        self._draw(self.quad_vao, 6,  x, y, w, h, cor)

    def desenha_hexagono(self, x, y, r, cor):
        self._draw(self.hexagon_vao, 18, x, y, r, r, cor)

    # ------------ “Computador” estilizado ------------ #
    def desenha_pc(self, x, y, scale=1.0, ativo=False):
        self.desenha_quad(x, y, 60*scale, 100*scale, np.array([0.3, 0.3, 0.3, 1.0], dtype=np.float32))
        self.desenha_quad(x, y+90*scale, 120*scale, 60*scale, np.array([0.2, 0.2, 0.2, 1.0], dtype=np.float32))
        cor_tela = np.array([0.8, 1.0, 0.8, 1.0], dtype=np.float32) if ativo else np.array([0.1, 0.1, 0.1, 1.0], dtype=np.float32)
        self.desenha_quad(x, y+90*scale, 100*scale, 40*scale, cor_tela)

    # ------ Desenha a mensagem com N hexágonos ------ #
    def desenha_mensagem(self, x, y, cores):
        base = 40  # raio do nível mais externo
        for i, cor in enumerate(cores):
            self.desenha_hexagono(x, y, base - i*6, cor)

# ============================================================ #
#                         Aplicação                             #
# ============================================================ #
class Application:
    def __init__(self):
        self.renderer = None

    # ------ Inicializa GLFW + contexto OpenGL ------ #
    def init(self):
        if not glfw.init():
            print("Falha ao iniciar GLFW")
            return False

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)

        self.window = glfw.create_window(WINDOW_WIDTH, WINDOW_HEIGHT, "Encapsulamento de Pacotes", None, None)
        if not self.window:
            glfw.terminate()
            print("Falha ao criar janela")
            return False

        glfw.make_context_current(self.window)
        glfw.set_key_callback(self.window, self.key_callback)
        glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)
        glClearColor(*BRANCO)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

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

    # ------------- Atualiza lógica/estados ------------- #
    def update(self):
        global estadoAtual, progressoAnimacao, mensagem_x

        # Fase de encapsulamento (sobre PC esquerdo)
        if ESTADOS["APLICACAO"] <= estadoAtual <= ESTADOS["FISICA"]:
            progressoAnimacao += velocidadeAnimacao
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0
                estadoAtual += 1
                if estadoAtual == ESTADOS["MOVE"]:  # inicia deslocamento
                    mensagem_x = 150

        # Movimento horizontal
        elif estadoAtual == ESTADOS["MOVE"]:
            progressoAnimacao += velocidadeAnimacao
            mensagem_x = 150 + (destino_x - 150) * progressoAnimacao
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0
                estadoAtual = ESTADOS["DFISICA"]
                mensagem_x = destino_x  # fixa posição final

        # Fase de desencapsulamento (sobre PC direito)
        elif ESTADOS["DFISICA"] <= estadoAtual <= ESTADOS["DTRANSPORTE"]:
            progressoAnimacao += velocidadeAnimacao
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0
                estadoAtual += 1
                if estadoAtual == ESTADOS["DONE"]:  # encerrou
                    estadoAtual = ESTADOS["IDLE"]
                    mensagem_x = 150

    # ------------------ Desenha cena ------------------ #
    def render(self):
        glClear(GL_COLOR_BUFFER_BIT)

        # Telas ativas conforme estado
        ativo_esq  = ESTADOS["APLICACAO"] <= estadoAtual <= ESTADOS["FISICA"]
        ativo_dir  = estadoAtual != ESTADOS["IDLE"] and estadoAtual >= ESTADOS["MOVE"]

        self.renderer.desenha_pc(150, 300, 1.0, ativo_esq)   # PC esquerdo
        self.renderer.desenha_pc(650, 300, 1.0, ativo_dir)   # PC direito

        # Seleciona cores por estado
        def cores_por_estado(st):
            if st in (ESTADOS["APLICACAO"], ESTADOS["DTRANSPORTE"]):  return [VERDE]
            if st in (ESTADOS["TRANSPORTE"], ESTADOS["DREDE"]):       return [AZUL, VERDE]
            if st in (ESTADOS["REDE"],       ESTADOS["DENLACE"]):     return [AMARELO, AZUL, VERDE]
            if st in (ESTADOS["ENLACE"],     ESTADOS["DFISICA"]):     return [VERMELHO, AMARELO, AZUL, VERDE]
            if st in (ESTADOS["FISICA"], ESTADOS["MOVE"]):            return [MAGENTA, VERMELHO, AMARELO, AZUL, VERDE]
            return []

        if estadoAtual != ESTADOS["IDLE"]:
            self.renderer.desenha_mensagem(mensagem_x, mensagem_y, cores_por_estado(estadoAtual))

    # ---------------- Callback de teclado ---------------- #
    def key_callback(self, window, key, scancode, action, mods):
        global estadoAtual, progressoAnimacao, mensagem_x
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_SPACE and estadoAtual == ESTADOS["IDLE"]:
            estadoAtual       = ESTADOS["APLICACAO"]
            progressoAnimacao = 0.0
            mensagem_x        = 150
            print("Iniciando animação...")
        elif key == glfw.KEY_R:
            estadoAtual       = ESTADOS["IDLE"]
            progressoAnimacao = 0.0
            mensagem_x        = 150
            print("Reset.")
        elif key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)

# ----------------------- Função main ----------------------- #
def main():
    app = Application()
    if app.init():
        app.run()
    return 0

if __name__ == "__main__":
    sys.exit(main())
