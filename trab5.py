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
mensagem_angulo = 0.0

# ----------------- Shaders GLSL ----------------- #

color_vertex_shader = """
#version 330 core
layout (location = 0) in vec2 position;

uniform mat4 model;
uniform mat4 projection;

void main()
{
    gl_Position = projection * model * vec4(position, 0.0, 1.0);
}
"""

color_fragment_shader = """
#version 330 core
out vec4 fragColor;
uniform vec4 color;

void main()
{
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

void main()
{
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

void main()
{
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
        self.text_shader = None
        self.quad_vao = None
        self.hexagon_vao = None
        self.projection = None

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
        glUniformMatrix4fv(
            glGetUniformLocation(self.color_shader, "projection"), 1, GL_FALSE, self.projection)
        glUseProgram(self.text_shader)
        glUniformMatrix4fv(
            glGetUniformLocation(self.text_shader, "projection"), 1, GL_FALSE, self.projection)

    def init_buffers(self):
        # Quad
        self.quad_vao = glGenVertexArrays(1)
        quad_vbo = glGenBuffers(1)
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
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # Hexágono
        self.hexagon_vao = glGenVertexArrays(1)
        hex_vbo = glGenBuffers(1)
        hex_vertices = [0.0, 0.0]
        hex_idx = []
        for i in range(6):
            ang = math.radians(60 * i)
            hex_vertices += [math.cos(ang), math.sin(ang)]
            hex_idx += [0, i + 1, i + 2] if i < 5 else [0, i + 1, 1]
        hex_vertices = np.array(hex_vertices, dtype=np.float32)
        hex_idx = np.array(hex_idx, dtype=np.uint32)

        glBindVertexArray(self.hexagon_vao)
        glBindBuffer(GL_ARRAY_BUFFER, hex_vbo)
        glBufferData(GL_ARRAY_BUFFER, hex_vertices.nbytes, hex_vertices, GL_STATIC_DRAW)
        ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, hex_idx.nbytes, hex_idx, GL_STATIC_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        glBindVertexArray(0)

    def _ortho(self, l, r, b, t):
        w, h = r - l, t - b
        ortho = np.identity(4, dtype=np.float32)
        ortho[0, 0] = 2.0 / w
        ortho[1, 1] = 2.0 / h
        ortho[3, 0] = -(r + l) / w
        ortho[3, 1] = -(t + b) / h
        ortho[2, 2] = -1.0
        return ortho

    def _draw(self, vao, count, x, y, sx, sy, cor):
        glUseProgram(self.color_shader)
        model = np.identity(4, dtype=np.float32)
        model[0, 0] = sx
        model[1, 1] = sy
        model[3, 0] = x
        model[3, 1] = y
        glUniformMatrix4fv(glGetUniformLocation(self.color_shader, "model"), 1, GL_FALSE, model)
        glUniform4fv(glGetUniformLocation(self.color_shader, "color"), 1, cor)
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)

    def desenha_quad(self, x, y, w, h, cor):
        self._draw(self.quad_vao, 6, x, y, w, h, cor)

    def desenha_hexagono(self, x, y, r, cor):
        self._draw(self.hexagon_vao, 18, x, y, r, r, cor)

    def desenha_pc(self, x, y, scale=1.0, ativo=False):
        self.desenha_quad(x, y, 60 * scale, 100 * scale, np.array([0.3, 0.3, 0.3, 1.0]))
        self.desenha_quad(x, y + 90 * scale, 120 * scale, 60 * scale, np.array([0.2, 0.2, 0.2, 1.0]))
        cor_tela = np.array([0.8, 1.0, 0.8, 1.0]) if ativo else np.array([0.1, 0.1, 0.1, 1.0])
        self.desenha_quad(x, y + 90 * scale, 100 * scale, 40 * scale, cor_tela)

    def _draw_rotated(self, vao, count, x, y, scale, rot_deg, cor):
        glUseProgram(self.color_shader)
        model = np.identity(4, dtype=np.float32)

        rad = math.radians(rot_deg)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)

        # rotação + escala 2D + translação (modelo 2D composto)
        model[0, 0] = cos_a * scale
        model[0, 1] = -sin_a * scale
        model[1, 0] = sin_a * scale
        model[1, 1] = cos_a * scale
        model[3, 0] = x
        model[3, 1] = y

        glUniformMatrix4fv(glGetUniformLocation(self.color_shader, "model"), 1, GL_FALSE, model)
        glUniform4fv(glGetUniformLocation(self.color_shader, "color"), 1, cor)

        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, count, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        

    def desenha_mensagem(self, x, y, cores, rot=0.0, scale=1.0):
        base = 40 * scale
        for i, cor in enumerate(cores):
            self._draw_rotated(self.hexagon_vao, 18, x, y, base - i * 6 * scale, rot, cor)

    def escreve_texto(self, x, y, texto, cor=(0.0, 0.0, 0.0)):
        from PIL import Image, ImageDraw, ImageFont

        font_size = 24
        font = ImageFont.truetype("arial.ttf", font_size)
        bbox = font.getbbox(texto)
        text_size = (bbox[2], bbox[3])

        image = Image.new("RGBA", text_size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), texto, font=font, fill=(int(cor[0]*255), int(cor[1]*255), int(cor[2]*255), 255))
        image_data = image.transpose(Image.FLIP_TOP_BOTTOM).tobytes()
        width, height = image.size

        texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, image_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        quad_vertices = np.array([
            x,         y,
            x + width, y,
            x + width, y + height,
            x,         y + height
        ], dtype=np.float32)

        tex_coords = np.array([
            0.0, 0.0,
            1.0, 0.0,
            1.0, 1.0,
            0.0, 1.0
        ], dtype=np.float32)

        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(2)

        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo[0])
        glBufferData(GL_ARRAY_BUFFER, quad_vertices.nbytes, quad_vertices, GL_STATIC_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, ctypes.c_void_p(0))

        glBindBuffer(GL_ARRAY_BUFFER, vbo[1])
        glBufferData(GL_ARRAY_BUFFER, tex_coords.nbytes, tex_coords, GL_STATIC_DRAW)
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 0, ctypes.c_void_p(0))

        glUseProgram(self.text_shader)
        model = np.identity(4, dtype=np.float32)
        glUniformMatrix4fv(glGetUniformLocation(self.text_shader, "model"), 1, GL_FALSE, model)
        glUniformMatrix4fv(glGetUniformLocation(self.text_shader, "projection"), 1, GL_FALSE, self.projection)
        glUniform4fv(glGetUniformLocation(self.text_shader, "color"), 1, np.append(cor, 1.0))
        glUniform1i(glGetUniformLocation(self.text_shader, "text"), 0)

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, texture)
        glBindVertexArray(vao)
        glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

        glBindVertexArray(0)
        glDeleteVertexArrays(1, [vao])
        glDeleteBuffers(2, vbo)
        glDeleteTextures([texture])





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
        global estadoAtual, progressoAnimacao, mensagem_x, mensagem_angulo

        if ESTADOS["APLICACAO"] <= estadoAtual <= ESTADOS["FISICA"]:
            progressoAnimacao += velocidadeAnimacao
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0
                estadoAtual += 1
                if estadoAtual == ESTADOS["MOVE"]:
                    mensagem_x = 150
                    mensagem_angulo = 0.0

        elif estadoAtual == ESTADOS["MOVE"]:
            progressoAnimacao += velocidadeAnimacao
            mensagem_x = 150 + (destino_x - 150) * progressoAnimacao
            mensagem_angulo += 5.0  # aumenta o ângulo de rotação
            if mensagem_angulo >= 360.0:
                mensagem_angulo -= 360.0
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0
                estadoAtual = ESTADOS["DFISICA"]
                mensagem_x = destino_x
                mensagem_angulo = 0.0

        elif ESTADOS["DFISICA"] <= estadoAtual <= ESTADOS["DTRANSPORTE"]:
            progressoAnimacao += velocidadeAnimacao
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0.0
                estadoAtual += 1
                if estadoAtual == ESTADOS["DONE"]:
                    estadoAtual = ESTADOS["IDLE"]
                    mensagem_x = 150

    # ------------------ Desenha cena ------------------ #
    def render(self):
        glClear(GL_COLOR_BUFFER_BIT)

        ativo_esq = ESTADOS["APLICACAO"] <= estadoAtual <= ESTADOS["FISICA"]
        ativo_dir = estadoAtual != ESTADOS["IDLE"] and estadoAtual >= ESTADOS["MOVE"]

        self.renderer.desenha_pc(150, 300, 1.0, ativo_esq)
        self.renderer.desenha_pc(650, 300, 1.0, ativo_dir)

        def cores_por_estado(st):
            if st in (ESTADOS["APLICACAO"], ESTADOS["DTRANSPORTE"]):  return [VERDE]
            if st in (ESTADOS["TRANSPORTE"], ESTADOS["DREDE"]):       return [AZUL, VERDE]
            if st in (ESTADOS["REDE"],       ESTADOS["DENLACE"]):     return [AMARELO, AZUL, VERDE]
            if st in (ESTADOS["ENLACE"],     ESTADOS["DFISICA"]):     return [VERMELHO, AMARELO, AZUL, VERDE]
            if st in (ESTADOS["FISICA"], ESTADOS["MOVE"]):            return [MAGENTA, VERMELHO, AMARELO, AZUL, VERDE]
            return []

        if estadoAtual != ESTADOS["IDLE"]:
            scale = 1.0
            if estadoAtual == ESTADOS["MOVE"]:
                scale = 1.0 - 0.5 * progressoAnimacao  # reduz até 0.5 do tamanho
            self.renderer.desenha_mensagem(mensagem_x, mensagem_y, cores_por_estado(estadoAtual), rot=mensagem_angulo, scale=scale)

            if estadoAtual == ESTADOS["APLICACAO"]:
                self.renderer.escreve_texto(80, 550, "Camada de Aplicacao: Mensagem original")
            elif estadoAtual == ESTADOS["TRANSPORTE"]:
                self.renderer.escreve_texto(80, 550, "Camada de Transporte: Cabecalho TCP/UDP")
            elif estadoAtual == ESTADOS["REDE"]:
                self.renderer.escreve_texto(80, 550, "Camada de Rede: Cabecalho IP")
            elif estadoAtual == ESTADOS["ENLACE"]:
                self.renderer.escreve_texto(80, 550, "Camada de Enlace: Cabecalho Ethernet")
            elif estadoAtual == ESTADOS["FISICA"]:
                self.renderer.escreve_texto(80, 550, "Camada Fisica: Sinais eletricos")
            elif estadoAtual == ESTADOS["DFISICA"]:
                self.renderer.escreve_texto(80, 550, "Recebendo na Fisica: Conversao de sinais")
            elif estadoAtual == ESTADOS["DENLACE"]:
                self.renderer.escreve_texto(80, 550, "Desencapsulando Enlace: Retira Ethernet")
            elif estadoAtual == ESTADOS["DREDE"]:
                self.renderer.escreve_texto(80, 550, "Desencapsulando Rede: Retira IP")
            elif estadoAtual == ESTADOS["DTRANSPORTE"]:
                self.renderer.escreve_texto(80, 550, "Desencapsulando Transporte: Retira TCP")
            elif estadoAtual == ESTADOS["DONE"]:
                self.renderer.escreve_texto(80, 550, "Mensagem recebida! Aplicacao finaliza")
        else:
            self.renderer.escreve_texto(200, 500, "Pressione ESPACO para iniciar a animacao")
            self.renderer.escreve_texto(150, 470, "Visualizacao do encapsulamento de pacotes")


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
