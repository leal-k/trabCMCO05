import numpy as np
import glfw
from OpenGL.GL import *
import OpenGL.GL.shaders as shaders
import math
import sys

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

BRANCO = np.array([1.0, 1.0, 1.0, 1.0], dtype=np.float32)
PRETO = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
VERMELHO = np.array([1.0, 0.0, 0.0, 1.0], dtype=np.float32)
VERDE = np.array([0.0, 1.0, 0.0, 1.0], dtype=np.float32)
AZUL = np.array([0.0, 0.0, 1.0, 1.0], dtype=np.float32)
AMARELO = np.array([1.0, 1.0, 0.0, 1.0], dtype=np.float32)
CIANO = np.array([0.0, 1.0, 1.0, 1.0], dtype=np.float32)
MAGENTA = np.array([1.0, 0.0, 1.0, 1.0], dtype=np.float32)


ESTADOS = {
    "IDLE": 0,
    "APLICACAO": 1,
    "TRANSPORTE": 2,
    "REDE": 3,
    "ENLACE": 4,
    "FISICA": 5
}

estadoAtual = ESTADOS["IDLE"]
progressoAnimacao = 0.0
velocidadeAnimacao = 0.005
mensagem = "Oi!"


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

text_vertex_shader = """
#version 330 core
layout (location = 0) in vec4 vertex; // <vec2 pos, vec2 tex>

out vec2 texCoords;

uniform mat4 projection;

void main()
{
    gl_Position = projection * vec4(vertex.xy, 0.0, 1.0);
    texCoords = vertex.zw;
}
"""

text_fragment_shader = """
#version 330 core
in vec2 texCoords;
out vec4 color;

uniform sampler2D text;
uniform vec4 textColor;

void main()
{    
    vec4 sampled = vec4(1.0, 1.0, 1.0, texture(text, texCoords).r);
    color = textColor * sampled;
}
"""

class Renderer:
    def __init__(self):
        self.shader = None
        self.text_shader = None
        
        self.quad_vao = None
        self.hexagon_vao = None
        self.text_vao = None
        
        self.projection = None
        
        self.characters = {}
    
    def init_shaders(self):
        self.shader = shaders.compileProgram(
            shaders.compileShader(vertex_shader, GL_VERTEX_SHADER),
            shaders.compileShader(fragment_shader, GL_FRAGMENT_SHADER)
        )
        
        self.text_shader = shaders.compileProgram(
            shaders.compileShader(text_vertex_shader, GL_VERTEX_SHADER),
            shaders.compileShader(text_fragment_shader, GL_FRAGMENT_SHADER)
        )
        
        self.projection = self.get_orthographic_projection(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
        
        glUseProgram(self.shader)
        projection_loc = glGetUniformLocation(self.shader, "projection")
        glUniformMatrix4fv(projection_loc, 1, GL_FALSE, self.projection)
        
        glUseProgram(self.text_shader)
        text_projection_loc = glGetUniformLocation(self.text_shader, "projection")
        glUniformMatrix4fv(text_projection_loc, 1, GL_FALSE, self.projection)
    
    def init_buffers(self): #cria vao e vbo
        self.quad_vao = glGenVertexArrays(1)
        quad_vbo = glGenBuffers(1)
        
        quad_vertices = np.array([
            -0.5, -0.5,
            0.5, -0.5,
            0.5, 0.5,
            -0.5, 0.5
        ], dtype=np.float32)
        
        quad_indices = np.array([
            0, 1, 2,
            0, 2, 3
        ], dtype=np.uint32)
        
        glBindVertexArray(self.quad_vao)
        
        glBindBuffer(GL_ARRAY_BUFFER, quad_vbo)
        glBufferData(GL_ARRAY_BUFFER, quad_vertices.nbytes, quad_vertices, GL_STATIC_DRAW)
        
        ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, quad_indices.nbytes, quad_indices, GL_STATIC_DRAW)
        
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        
        self.hexagon_vao = glGenVertexArrays(1)
        hexagon_vbo = glGenBuffers(1)
        
        hexagon_vertices = []
        hexagon_indices = []
        
        hexagon_vertices.extend([0.0, 0.0]) #meio do hexagono
        
        for i in range(6): #vertice do hexagono
            angle = math.radians(60 * i)
            hexagon_vertices.extend([math.cos(angle), math.sin(angle)])
            if i < 5:
                hexagon_indices.extend([0, i+1, i+2])
            else:
                hexagon_indices.extend([0, i+1, 1])
        
        hexagon_vertices = np.array(hexagon_vertices, dtype=np.float32)
        hexagon_indices = np.array(hexagon_indices, dtype=np.uint32)
        
        glBindVertexArray(self.hexagon_vao)
        
        glBindBuffer(GL_ARRAY_BUFFER, hexagon_vbo)
        glBufferData(GL_ARRAY_BUFFER, hexagon_vertices.nbytes, hexagon_vertices, GL_STATIC_DRAW)
        
        hexagon_ebo = glGenBuffers(1)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, hexagon_ebo)
        glBufferData(GL_ELEMENT_ARRAY_BUFFER, hexagon_indices.nbytes, hexagon_indices, GL_STATIC_DRAW)
        
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * 4, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        
        glBindVertexArray(0) #limpa o vao
        
        self.init_text_system()
    
    def init_text_system(self):
        
        self.text_vao = glGenVertexArrays(1) #vao e vbo pro texto
        text_vbo = glGenBuffers(1)
        
        glBindVertexArray(self.text_vao)
        glBindBuffer(GL_ARRAY_BUFFER, text_vbo)
        glBufferData(GL_ARRAY_BUFFER, 6 * 4 * 4, None, GL_DYNAMIC_DRAW)  #6 vertices, 4 componentes cada
        
        glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 0, ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)
        
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
    
    def get_orthographic_projection(self, left, right, bottom, top): #matriz de projeção
        width = right - left
        height = top - bottom
        
        ortho = np.identity(4, dtype=np.float32)
        ortho[0, 0] = 2.0 / width
        ortho[1, 1] = 2.0 / height
        ortho[2, 2] = -1.0
        ortho[3, 0] = -(right + left) / width
        ortho[3, 1] = -(top + bottom) / height
        
        return ortho
    
    def desenha_quad(self, pos_x, pos_y, largura, altura, cor):
        glUseProgram(self.shader)
        
        model = np.identity(4, dtype=np.float32) #matriz modelo
        model[0, 0] = largura
        model[1, 1] = altura
        model[3, 0] = pos_x
        model[3, 1] = pos_y
        
        model_loc = glGetUniformLocation(self.shader, "model")
        color_loc = glGetUniformLocation(self.shader, "color")
        
        glUniformMatrix4fv(model_loc, 1, GL_FALSE, model)
        glUniform4fv(color_loc, 1, cor)
        
        glBindVertexArray(self.quad_vao) #desenha quadrado
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
    
    def desenha_hexagono(self, pos_x, pos_y, raio, cor):
        glUseProgram(self.shader)
        
        model = np.identity(4, dtype=np.float32) #matreiz modelo
        model[0, 0] = raio
        model[1, 1] = raio
        model[3, 0] = pos_x
        model[3, 1] = pos_y
        
        model_loc = glGetUniformLocation(self.shader, "model")
        color_loc = glGetUniformLocation(self.shader, "color")
        
        glUniformMatrix4fv(model_loc, 1, GL_FALSE, model)
        glUniform4fv(color_loc, 1, cor)
        
        glBindVertexArray(self.hexagon_vao) #desenha hexagono
        glDrawElements(GL_TRIANGLES, 18, GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
    
    def escreve_texto(self, texto, pos_x, pos_y, escala=1.0, cor=PRETO):
        print(f"Texto: '{texto}' em ({pos_x}, {pos_y})") #teste que aparece o texto no terminal
        #terminar de implementar
        
    
    def desenha_pc(self, x, y, scale=1.0, active=False):
        cor_base = np.array([0.3, 0.3, 0.3, 1.0], dtype=np.float32) #desenha base do pc
        self.desenha_quad(x, y, 60 * scale, 100 * scale, cor_base)
        
        cor_suporte = np.array([0.2, 0.2, 0.2, 1.0], dtype=np.float32) #desenha suporte do monitor
        self.desenha_quad(x, y + 90 * scale, 120 * scale, 60 * scale, cor_suporte)
        
        if active: #desenha a tela ativa ou inativa
            cor_tela = np.array([0.8, 1.0, 0.8, 1.0], dtype=np.float32)  # Verde claro para tela ativa
        else:
            cor_tela = np.array([0.1, 0.1, 0.1, 1.0], dtype=np.float32)  # Preto para tela inativa
        
        self.desenha_quad(x, y + 90 * scale, 100 * scale, 40 * scale, cor_tela)
    
    def desenha_mensagem(self, x, y, texto, nivelCor=None, rotation=0): #desenha as camadas
        if nivelCor:
            raioNivel = 40
            for i, cor in enumerate(nivelCor):
                raio = raioNivel - i * 6
                self.desenha_hexagono(x, y, raio, cor)


class Application:
    def __init__(self):
        self.renderer = None
        
    def init(self):
        if not glfw.init(): #inicia glfw
            print("Não foi possível inicializar o GLFW")
            return False
        
        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        
        #cria a janela
        self.window = glfw.create_window(WINDOW_WIDTH, WINDOW_HEIGHT, "Encapsulamento de Pacotes na Rede", None, None)
        if not self.window:
            print("Não foi possível criar a janela GLFW")
            glfw.terminate()
            return False
        
        glfw.make_context_current(self.window) #faz a janela atual
        
        glfw.set_key_callback(self.window, self.key_callback) #configura callback
        
        glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT) #configura openGL
        glClearColor(*BRANCO)
        
        glEnable(GL_BLEND) #blend pra transparência
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        self.renderer = Renderer() #inicia renderer
        self.renderer.init_shaders()
        self.renderer.init_buffers()
        
        print("OpenGL inicializado com sucesso.")
        print(f"Versão: {glGetString(GL_VERSION).decode()}")
        
        return True
    
    def run(self):
        print("Pressione ESPAÇO para iniciar a animação, R para resetar, ESC para sair")
        
        #loop principal
        while not glfw.window_should_close(self.window):
            glfw.poll_events()
            
            self.update()
            
            self.render()
            
            glfw.swap_buffers(self.window)

        glfw.terminate()
    
    def update(self): #função pra atualizar a animação a cada iteração
        global estadoAtual, progressoAnimacao
        
        if estadoAtual != ESTADOS["IDLE"]:
            progressoAnimacao += velocidadeAnimacao
            if progressoAnimacao >= 1.0:
                progressoAnimacao = 0
                estadoAtual += 1
                if estadoAtual > ESTADOS["FISICA"]: #volta pra idle, "fim da animação"
                    estadoAtual = ESTADOS["IDLE"]
                    print("Animação completa")
    
    def render(self):
        glClear(GL_COLOR_BUFFER_BIT)
        
        self.renderer.desenha_pc(150, 300, 1.0, estadoAtual >= ESTADOS["APLICACAO"])
        self.renderer.desenha_pc(650, 300, 1.0, estadoAtual >= ESTADOS["APLICACAO"])
        
        nivelCor = []
        texto_info = ""
        
        if estadoAtual == ESTADOS["APLICACAO"]:
            nivelCor = [VERDE]
            texto_info = "Camada de Aplicacao: Mensagem original"
        elif estadoAtual == ESTADOS["TRANSPORTE"]:
            nivelCor = [AZUL, VERDE]
            texto_info = "Camada de Transporte: Cabecalho TCP/UDP"
        elif estadoAtual == ESTADOS["REDE"]:
            nivelCor = [AMARELO, AZUL, VERDE]
            texto_info = "Camada de Rede: Cabecalho IP"
        elif estadoAtual == ESTADOS["ENLACE"]:
            nivelCor = [VERMELHO, AMARELO, AZUL, VERDE]
            texto_info = "Camada de Enlace: Cabecalho Ethernet"
        elif estadoAtual == ESTADOS["FISICA"]:
            nivelCor = [MAGENTA, VERMELHO, AMARELO, AZUL, VERDE]
            texto_info = "Camada Fisica: Sinais eletricos"
        else: #idle
            self.renderer.escreve_texto("Pressione ESPACO para iniciar a animacao", 300, 500)
            self.renderer.escreve_texto("Demonstracao de encapsulamento de pacotes na rede", 200, 450)
        
        if nivelCor:
            self.renderer.desenha_mensagem(150, 200, mensagem, nivelCor)
            self.renderer.escreve_texto(texto_info, 90, 425)
    
    def key_callback(self, window, key, scancode, action, mods):
        global estadoAtual, progressoAnimacao
        
        if action == glfw.PRESS:
            if key == glfw.KEY_SPACE and estadoAtual == ESTADOS["IDLE"]:
                estadoAtual = ESTADOS["APLICACAO"]
                progressoAnimacao = 0
                print("Iniciando animação")
            elif key == glfw.KEY_R:
                estadoAtual = ESTADOS["IDLE"]
                progressoAnimacao = 0
                print("Resetando animação")
            elif key == glfw.KEY_ESCAPE:
                print("Encerrando programa")
                glfw.set_window_should_close(window, True)


def main():
    app = Application()
    if app.init():
        app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())