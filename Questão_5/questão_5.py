"""
SHELL DE SISTEMA BASEADO EM CONHECIMENTO 

  USUÁRIO -> INTERFACE -> ENGENHO DE INFERÊNCIA <-> EXPLICAÇÃO
                                 |
                         BASE DE CONHECIMENTO <- EDITOR DA BASE

  1. BaseConhecimento : fatos + regras SE ... ENTAO ... (salva/carrega JSON)
  2. EditorBC         : criar / editar / excluir regras e fatos
  3. Motor            : encadeamento p/ frente, p/ trás e misto
                        + explicação: POR QUÊ?, COMO?, trilha de inferência
  4. Interface        : diálogo (comandos + frases simples em português)

Uso:  python sbc_shell.py animais.json
"""
import json, re, unicodedata
from dataclasses import dataclass, field


def norm(s):
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower().strip()

def attr_id(s):
    return re.sub(r"\s+", "_", norm(s))

def igual(a, b):
    return norm(a) == norm(b)

def sim_nao(t):
    t = norm(t)
    return "sim" if t in ("s", "sim", "yes", "y") else "nao" if t in ("n", "nao", "no") else None

def tokens(s):
    parar = {"o", "a", "os", "as", "um", "uma", "de", "do", "da", "que", "e", "em", "voce",
             "qual", "quem", "eh", "foi", "ser", "se", "me", "para", "por"}
    return {t for t in re.findall(r"[a-z0-9]+", norm(s)) if t not in parar}


def parse_cond(txt):
    txt = txt.strip()
    if "=" in txt:
        a, v = txt.split("=", 1)
        return attr_id(a), v.strip().strip("\"'")
    m = re.match(r"(?i)^n[aã]o\s+(.+)$", txt)
    return (attr_id(m[1]), "nao") if m else (attr_id(txt), "sim")

def cond_str(c):
    return f"{c[0]} = {c[1]}"

@dataclass
class Regra:
    id: str
    se: list          
    entao: tuple      

    def __str__(self):
        return f"{self.id}: SE {' E '.join(map(cond_str, self.se))} ENTÃO {cond_str(self.entao)}"

RE_REGRA = re.compile(r"^\s*(?:([\w.\-]+)\s*:\s*)?SE\s+(.+?)\s+ENT[AÃ]O\s+(.+?)\s*$", re.I)

def parse_regra(txt, id_auto):
    m = RE_REGRA.match(txt)
    if not m:
        raise ValueError("sintaxe: [ID:] SE cond E cond ... ENTAO atributo = valor")
    return Regra(m[1] or id_auto, [parse_cond(p) for p in re.split(r"\s+E\s+", m[2])], parse_cond(m[3]))


class BaseConhecimento:
    def __init__(self, nome="Nova base"):
        self.nome, self.fatos, self.regras, self.perguntas = nome, {}, [], {}

    def regra(self, rid):
        return next((r for r in self.regras if norm(r.id) == norm(rid)), None)

    def concluem(self, attr):
        return [r for r in self.regras if r.entao[0] == attr]

    def atributos(self):
        s = set(self.fatos) | {r.entao[0] for r in self.regras} | {c[0] for r in self.regras for c in r.se}
        return sorted(s)

    def primitivos(self):
        res = []
        for r in self.regras:
            for a, _ in r.se:
                if a not in res and not self.concluem(a):
                    res.append(a)
        return res

    def objetivos(self):
        usados = {c[0] for r in self.regras for c in r.se}
        return [a for a in self.atributos() if self.concluem(a) and a not in usados]

    def valores(self, attr):
        vals = []
        for r in self.regras:
            for a, v in r.se + [r.entao]:
                if a == attr and norm(v) not in ("sim", "nao") and v not in vals:
                    vals.append(v)
        return vals

    def pergunta(self, attr):
        return self.perguntas.get(attr) or attr.replace("_", " ").capitalize() + "?"

    def salvar(self, caminho):
        d = {"nome": self.nome, "perguntas": self.perguntas, "fatos": self.fatos,
             "regras": [str(r) for r in self.regras]}
        json.dump(d, open(caminho, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    @staticmethod
    def carregar(caminho):
        d = json.load(open(caminho, encoding="utf-8"))
        bc = BaseConhecimento(d.get("nome", "Base"))
        bc.perguntas = {attr_id(k): v for k, v in d.get("perguntas", {}).items()}
        bc.fatos = {attr_id(k): v for k, v in d.get("fatos", {}).items()}
        for i, t in enumerate(d.get("regras", []), 1):
            bc.regras.append(parse_regra(t, f"R{i}"))
        return bc


AJUDA_EDITOR = """EDITOR DA BASE
  listar                          mostra fatos e regras
  regra [ID:] SE a = x E b ENTAO c = y    cria regra (ID automático se omitido)
  editar ID SE ... ENTAO ...      substitui a regra ID
  excluir ID                      remove a regra
  fato atributo = valor           cria/atualiza fato inicial
  excluir fato atributo           remove fato
  pergunta atributo | texto       define a pergunta feita ao usuário
  salvar arq.json | sair"""

class EditorBC:
    def __init__(self, bc):
        self.bc = bc

    def executar(self, linha):
        bc = self.bc
        cmd, _, arg = linha.strip().partition(" ")
        arg = arg.strip()
        c = norm(cmd)
        
        if c == "listar":
            print("FATOS:", *[f"\n  {a} = {v}" for a, v in bc.fatos.items()] or ["(nenhum)"])
            print("REGRAS:", *[f"\n  {r}" for r in bc.regras] or ["(nenhuma)"])
        elif c == "regra" or RE_REGRA.match(linha):
            r = parse_regra(arg if c == "regra" else linha, f"R{len(bc.regras) + 1}")
            if bc.regra(r.id):
                raise ValueError(f"já existe a regra {r.id}")
            bc.regras.append(r)
            print("  criada:", r)
        elif c == "editar":
            rid, _, txt = arg.partition(" ")
            antiga = bc.regra(rid)
            if not antiga:
                raise ValueError(f"regra {rid} não existe")
            nova = parse_regra(txt, antiga.id)
            nova.id = antiga.id
            bc.regras[bc.regras.index(antiga)] = nova
            print("  atualizada:", nova)
        elif c == "excluir":
            if norm(arg).startswith("fato "):
                if bc.fatos.pop(attr_id(arg[5:]), None) is None:
                    raise ValueError("fato não existe")
            else:
                r = bc.regra(arg)
                if not r:
                    raise ValueError(f"regra {arg} não existe")
                bc.regras.remove(r)
            print("  excluído.")
        elif c == "fato":
            a, v = parse_cond(arg)
            bc.fatos[a] = v
            print(f"  fato: {a} = {v}")
        elif c == "pergunta":
            a, _, txt = arg.partition("|")
            bc.perguntas[attr_id(a)] = txt.strip()
        elif c == "salvar":
            bc.salvar(arg or "base.json")
            print("  salvo.")
        elif c == "ajuda":
            print(AJUDA_EDITOR)
        elif linha.strip():
            raise ValueError("comando desconhecido (digite 'ajuda')")

    def loop(self):
        print("── EDITOR DA BASE ── ('ajuda' lista comandos, 'sair' volta)")
        while True:
            try:
                linha = input("bc> ")
            except EOFError:
                return
            if norm(linha) == "sair":
                return
            try:
                self.executar(linha)
            except ValueError as e:
                print("  erro:", e)


# inferência
@dataclass
class Fato:
    valor: str
    origem: str                       # "base" | "usuario" | id da regra 
    premissas: list = field(default_factory=list)

class Abortar(Exception):
    pass

class Motor:
    def __init__(self, bc, io):
        self.bc, self.io = bc, io
        self.reiniciar()

    def reiniciar(self, extras=None):
        self.mem, self.trilha = {}, []                       
        self.feitas, self.falhas = set(), set()              
        self.nao_sabe, self.em_prova = set(), set()
        self.pilha, self.modo, self.objetivo = [], None, None  
        for a, v in {**self.bc.fatos, **(extras or {})}.items():
            self.mem[a] = Fato(v, "base" if a in self.bc.fatos else "usuario")
            self.log(f"Fato inicial: {a} = {v}")

    def log(self, msg):
        self.trilha.append(f"{len(self.trilha) + 1:>3}. {msg}")

    def disparar(self, r):
        self.feitas.add(r.id)
        a, v = r.entao
        if a not in self.mem:
            self.mem[a] = Fato(v, r.id, [c[0] for c in r.se])
            self.log(f"Regra {r.id} disparada => {a} = {v}")

    def verdadeira(self, c):
        f = self.mem.get(c[0])
        return f is not None and igual(f.valor, c[1])

    # encadeamento para frente
    def propagar(self):
        mudou = True
        while mudou:
            mudou = False
            for r in self.bc.regras:
                if r.id not in self.feitas and r.entao[0] not in self.mem \
                        and all(self.verdadeira(c) for c in r.se):
                    self.disparar(r)
                    mudou = True

    def frente(self):
        self.modo = "frente"
        self.log("Encadeamento para FRENTE")
        for a in self.bc.primitivos():
            if a not in self.mem:
                r = next(r for r in self.bc.regras for c in r.se if c[0] == a)
                self.pilha = [(r, next(c for c in r.se if c[0] == a))]
                self.perguntar(a)
        self.pilha = []
        self.propagar()

    # encadeamento para trás
    def tras(self, attr, valor=None):
        self.modo, self.objetivo, self.pilha = self.modo or "tras", attr, []
        self.log(f"Encadeamento para TRÁS - objetivo: {attr}" + (f" = {valor}" if valor else ""))
        return self.provar(attr, valor)

    def provar(self, attr, valor=None):
        if attr in self.mem:
            return self.mem[attr]
        if attr in self.nao_sabe or attr in self.em_prova:
            return None
            
        self.em_prova.add(attr)
        regras = self.bc.concluem(attr)
        if valor:
            regras = [r for r in regras if igual(r.entao[1], valor)]
            
        for r in regras:
            if attr in self.mem:
                break
            if r.id in self.feitas or r.id in self.falhas:
                continue
            self.log(f"Tentando {r.id} para provar {attr}")
            if self.provar_regra(r):
                self.disparar(r)
                
        self.em_prova.discard(attr)
        if attr in self.mem:
            return self.mem[attr]
        return None if self.bc.concluem(attr) else self.perguntar(attr)

    def provar_regra(self, r):
        for c in sorted(r.se, key=lambda c: c[0] not in self.mem):
            self.pilha.append((r, c))
            f = self.provar(c[0], c[1])
            self.pilha.pop()
            if not (f and igual(f.valor, c[1])):
                self.falhas.add(r.id)
                self.log(f"Regra {r.id} descartada: '{cond_str(c)}' nao satisfeita")
                return False
        return True

    # encadeamento misto
    def misto(self, attr):
        self.modo = "misto"
        self.log("Encadeamento MISTO")
        self.propagar()
        return self.tras(attr)

    def perguntar(self, attr):
        while True:
            resp = self.io.perguntar(attr)
            n = norm(resp)
            if n in ("por que", "porque", "?", "pq"):
                print(self.por_que(attr))
            elif n in ("nao sei", "ns", "desconhecido"):
                self.nao_sabe.add(attr)
                self.log(f"Usuário não sabe: {attr}")
                return None
            elif n in ("abortar", "parar"):
                raise Abortar()
            elif n:
                vals = self.bc.valores(attr)
                v = sim_nao(resp) or (vals[int(n) - 1] if n.isdigit() and 0 < int(n) <= len(vals) else resp.strip())
                self.mem[attr] = Fato(v, "usuario")
                self.log(f"Usuário respondeu: {attr} = {v}")
                if self.modo == "misto":
                    self.propagar()
                return self.mem[attr]

    def por_que(self, attr):
        if not self.pilha:
            return f"  Pergunto '{attr}' porque é o objetivo da consulta e nenhuma regra deduz isso."
            
        r, c = self.pilha[-1]
        if self.modo == "frente":
            linhas = [f"  Coletando dados de entrada: '{attr}' é usado na regra {r.id}."]
        else:
            linhas = [f"  Preciso de '{attr}' para verificar '{cond_str(c)}' da regra {r.id}."]
            
        linhas.append(f"    {r}")
        
        for i in range(len(self.pilha) - 2, -1, -1):
            interna, (externa, cond) = self.pilha[i + 1][0], self.pilha[i]
            linhas.append(f"  E a regra {interna.id}? Porque concluiria {cond_str(interna.entao)}, "
                     f"necessário para '{cond_str(cond)}' da regra {externa.id}.")
                     
        if self.objetivo and self.modo != "frente":
            linhas.append(f"  Tudo isso para chegar no objetivo final: '{self.objetivo}'.")
        return "\n".join(linhas)

    def como(self, attr, nivel=0):
        f, ind = self.mem.get(attr), "   " * nivel
        if not f:
            return [f"{ind}{attr}: desconhecido"]
            
        if f.origem in ("base", "usuario"):
            fonte = 'fato da base' if f.origem == 'base' else 'informado pelo usuario'
            return [f"{ind}{attr} = {f.valor}   [{fonte}]"]
            
        linhas = [f"{ind}{attr} = {f.valor}   [deduzido por {self.bc.regra(f.origem) or f.origem}]"]
        for p in f.premissas:
            linhas += self.como(p, nivel + 1)
        return linhas


# interface 
AJUDA = """COMANDOS
  carregar arq.json | salvar arq.json | editor | regras | fatos
  frente                encadeamento para frente
  tras [objetivo]       encadeamento para trás   (ex.: tras animal  |  tras animal = tigre)
  misto [objetivo]      encadeamento misto
  como [atributo]       COMO a conclusão foi obtida      trilha   passos da inferência
  informar a = valor    informa um fato                  reiniciar | sair
Durante uma pergunta: responda, ou digite 'por que' (POR QUÊ?), 'nao sei', 'abortar'.
Frases em português também funcionam, por exemplo:
  "qual é o animal?"   "o animal é um tigre?"   "o animal tem penas"   "o animal não voa"
  "como você concluiu o animal?"   "o que você consegue deduzir?"   "use o misto para descobrir o animal" """

class Interface:
    def __init__(self, bc=None):
        self.bc = bc or BaseConhecimento()
        self.informados = {}
        self.refazer_motor()

    def refazer_motor(self):
        self.motor = Motor(self.bc, self)

    def perguntar(self, attr):                     
        print(f"\n? {self.bc.pergunta(attr)}")
        for i, v in enumerate(self.bc.valores(attr), 1):
            print(f"   {i}) {v}")
        try:
            return input("  [resposta | por que | nao sei] » ")
        except EOFError:
            raise Abortar()

    def carregar(self, caminho):
        try:
            self.bc = BaseConhecimento.carregar(caminho)
        except (OSError, ValueError, KeyError) as e:
            print("erro ao carregar:", e)
            return
        self.informados = {}
        self.refazer_motor()
        print(f"Base '{self.bc.nome}': {len(self.bc.regras)} regras, {len(self.bc.fatos)} fatos.")

    def achar_attr(self, texto, candidatos):
        tt, melhor = tokens(texto), (0, None)
        for a in candidatos:
            ref = tokens(a.replace("_", " ") + " " + self.bc.perguntas.get(a, ""))
            if len(ref & tt) > melhor[0]:
                melhor = (len(ref & tt), a)
        return melhor[1]

    def objetivo_de(self, texto):
        t = texto.strip().rstrip("?")
        if "=" in t:
            return parse_cond(t)
        a = attr_id(t) if attr_id(t) in self.bc.atributos() else \
            self.achar_attr(t, [x for x in self.bc.atributos() if self.bc.concluem(x)])
        v = next((v for v in self.bc.valores(a) if norm(v) in norm(t)), None) if a else None
        return a, v

    def executar(self, modo, texto=""):
        if not self.bc.regras:
            return print("Base vazia: use 'editor' ou 'carregar'.")
        self.motor.reiniciar(self.informados)
        m = self.motor
        try:
            if modo == "frente":
                m.frente()
                novos = {a: f for a, f in m.mem.items() if f.origem not in ("base", "usuario")}
                print("\n── RESULTADO ──" if novos else "\nNenhuma conclusão com os dados informados.")
                for a, f in novos.items():
                    print(f"  {'*' if a in self.bc.objetivos() else '-'} {a} = {f.valor}   (regra {f.origem})")
                return
            a, v = self.objetivo_de(texto) if texto.strip() else (None, None)
            if texto.strip() and not a:
                return print("Objetivo não identificado. Possíveis:", ", ".join(self.bc.objetivos()))
            for alvo in [a] if a else self.bc.objetivos():
                f = m.tras(alvo, v) if modo == "tras" else m.misto(alvo)
                if f:
                    break
            if f and (not v or igual(f.valor, v)):
                print(f"\n── RESULTADO ──\n  > {alvo} = {f.valor}   (digite 'como {alvo}' para a justificativa)")
            else:
                print("\n── RESULTADO ──\n  > Não foi possível estabelecer o objetivo.")
        except Abortar:
            print("\nConsulta abortada.")

    def comando_como(self, texto):
        a = attr_id(texto) if attr_id(texto) in self.motor.mem else self.achar_attr(texto, self.motor.mem)
        if not a:
            a = next((x for x in self.bc.objetivos() if x in self.motor.mem), None)
        print("\n".join(self.motor.como(a)) if a else "Nada a explicar ainda (faça uma consulta).")

    def frase(self, linha):
        n = norm(linha)
        if n.startswith("como"):
            self.comando_como(re.sub(r"^como (voce )?(chegou|concluiu|sabe|deduziu|obteve|descobriu)?( que| a| o)?", "", n))
        elif "misto" in n:
            self.executar("misto", re.sub(r".*(misto|descobrir|determinar)\s*(para)?\s*(descobrir)?", "", n))
        elif re.search(r"para frente|deduz|conclu|inferi", n) and not n.startswith(("qual", "quem")):
            self.executar("frente")
        elif re.match(r"^(qual|quem|que|o que|descubra|identifique|determine|diagnostique|recomende)\b", n) \
                or n.endswith("?"):
            a, v = self.objetivo_de(n)
            if not a:
                return print("Não identifiquei o objetivo. Possíveis:", ", ".join(self.bc.objetivos()))
            print(f"Entendi: {'verificar ' + a + ' = ' + v if v else 'descobrir ' + a}")
            self.executar("tras", f"{a} = {v}" if v else a)
        else:                                           
            a = self.achar_attr(n, self.bc.primitivos())
            if not a:
                return print("Não entendi. Digite 'ajuda'.")
            v = next((v for v in self.bc.valores(a) if norm(v) in n), None) \
                or ("nao" if re.search(r"\b(nao|nunca|sem)\b", n) else "sim")
            self.informados[a] = v
            print(f"Entendi: {a} = {v}")

    def comando(self, linha):
        cmd, _, arg = linha.strip().partition(" ")
        c, arg = norm(cmd), arg.strip()
        if c in ("sair", "exit", "quit"):
            return False
        if c == "ajuda":
            print(AJUDA)
        elif c == "carregar":
            self.carregar(arg)
        elif c == "salvar":
            self.bc.salvar(arg or "base.json")
            print("Base salva.")
        elif c == "editor":
            EditorBC(self.bc).loop()
            self.informados = {}
        elif c in ("frente", "tras", "misto"):
            self.executar(c, arg)
        elif c == "como":
            self.comando_como(arg)
        elif c == "trilha":
            print("\n".join(self.motor.trilha) or "(vazia)")
        elif c == "regras":
            print("\n".join(map(str, self.bc.regras)) or "(nenhuma)")
        elif c == "fatos":
            for a, f in self.motor.mem.items():
                print(f"  {a} = {f.valor}   [{f.origem}]")
            for a, v in self.informados.items():
                print(f"  {a} = {v}   [informado]")
        elif c == "informar":
            a, v = parse_cond(arg)
            self.informados[a] = v
        elif c == "reiniciar":
            self.informados = {}
            self.motor.reiniciar()
            print("Memória limpa.")
        elif linha.strip():
            self.frase(linha)
        return True

    def run(self):
        print("=== SHELL GENÉRICO DE SBC === ('ajuda' lista os comandos)")
        while True:
            try:
                if not self.comando(input("\nsbc> ")):
                    break
            except (EOFError, KeyboardInterrupt):
                break
            except ValueError as e:
                print("erro:", e)
        print("Até logo.")


if __name__ == "__main__":
    import sys
    ui = Interface()
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-f'):
        ui.carregar(sys.argv[1])
    ui.run()