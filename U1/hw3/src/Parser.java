import java.math.BigInteger;
import java.util.Scanner;

public class Parser {

    private Lexer lexer;

    private FuncReg registry;

    public Parser(Lexer lexer, FuncReg registry) {
        this.lexer = lexer;
        this.registry = registry;
    }

    public Parser(FuncReg registry) {
        this(null, registry);
    }

    private Parser childParser(String text) {
        return new Parser(new Lexer(text), registry);
    }

    public Expr parseExprFromText(String text) {
        return childParser(Processor.preprocess(text)).parseExpr();
    }

    public void parseFuncDef(Scanner sc) {
        String s = Processor.preprocess(sc.nextLine());
        String[] parts = s.split("=", 2);
        if (parts.length < 2) {
            return;
        }
        String body = parts[1];
        Parser parser = childParser(body);
        registry.setFuncDef(new FuncReg.FuncDef(parser.parseExpr()));
    }

    public void parseRecDef(Scanner sc) {
        FuncReg.RecDef recDef = new FuncReg.RecDef();
        for (int i = 0; i < 3; i++) {
            String line = Processor.preprocess(sc.nextLine());
            String[] parts = line.split("=", 2);
            if (parts.length < 2) {
                continue;
            }
            String head = parts[0];
            String body = parts[1];

            Parser parser = childParser(body);
            if (head.contains("{0}")) {
                recDef.setF0Body(parser.parseExpr());
            } else if (head.contains("{1}")) {
                recDef.setF1Body(parser.parseExpr());
            } else {
                parser.parseRecTemplate(recDef);
            }
        }
        registry.setRecDef(recDef);
    }

    private void parseRecTemplate(FuncReg.RecDef def) {
        def.setC1(parseInteger());
        consume("*");
        consumeHead("1");
        def.setArg1(parseFactor());
        consume(")");

        int sign = parseSign();

        BigInteger c2 = parseInteger();
        if (sign < 0) {
            c2 = c2.negate();
        }
        def.setC2(c2);
        consume("*");
        consumeHead("2");
        def.setArg2(parseFactor());
        consume(")");

        if ("+".equals(lexer.peek()) || "-".equals(lexer.peek())) {
            def.setExtraBody(parseExpr());
        }
    }

    private BigInteger parseInteger() {
        int sign = parseSign();
        BigInteger value = new BigInteger(lexer.peek());
        lexer.next();
        return sign > 0 ? value : value.negate();
    }

    private int parseSign() {
        int sign = 1;
        while ("+".equals(lexer.peek()) || "-".equals(lexer.peek())) {
            if ("-".equals(lexer.peek())) {
                sign = -sign;
            }
            lexer.next();
        }
        return sign;
    }

    private void consumeHead(String index) {
        consume("f");
        consume("{");
        consume("n");
        consume("-");
        consume(index);
        consume("}");
        consume("(");
    }

    private void consume(String token) {
        if (token == null || token.equals(lexer.peek())) {
            lexer.next();
        }
    }

    // 表达式 -> [加减] 项 { 加减 项 }
    public Expr parseExpr() {
        Expr expr = new Expr();
        expr.addTerm(parseTerm());

        while ("+".equals(lexer.peek()) || "-".equals(lexer.peek())) {
            int sign = parseSign();
            Term term = parseTerm();
            if (sign < 0) {
                term.negate();
            }
            expr.addTerm(term);
        }
        return expr;
    }

    // 项 -> [加减] 因子 { '*' 因子 }
    public Term parseTerm() {
        Term term = new Term();
        int sign = parseSign();
        term.addFactor(parseFactor());
        if (sign < 0) {
            term.negate();
        }
        while ("*".equals(lexer.peek())) {
            consume("*");
            term.addFactor(parseFactor());
        }
        return term;
    }

    // 因子 -> 变量因子 | 常数因子 | 表达式因子 | 选择式因子 | 求导因子
    public Factor parseFactor() {
        String s = lexer.peek();
        if ("x".equals(s) || "y".equals(s)) { //变量因子/幂函数/自变量
            return parsePower();
        } else if ("exp".equals(s)) { //变量因子/指数函数
            return parseExpFactor();
        } else if ("f".equals(s)) { //变量因子/函数调用
            return parseFuncFactor();
        } else if ("(".equals(s)) { //表达式因子
            return parseExprFactor();
        } else if ("[".equals(s)) { //选择式因子
            return parseChoiceFactor();
        } else if ("dx".equals(s) || "dy".equals(s) || "grad".equals(s)) { //求导因子
            return parseDeriveFactor();
        } else { //常数因子
            return parseNumber();
        }
    }

    // 求导因子 -> 'dx' '(' 表达式 ')' | 'dy' '(' 表达式 ')' | 'grad' '(' 表达式 ')'
    public DeriveFactor parseDeriveFactor() {
        String deriveType = lexer.peek();
        lexer.next();
        Expr argument = parseExprFactor();
        return new DeriveFactor(deriveType, argument);
    }

    // 常数因子 -> 带符号的整数
    public Number parseNumber() {
        BigInteger num = parseInteger();
        return new Number(num);
    }

    // 变量因子 -> 幂函数 | 指数函数 | 函数调用
    // 幂函数 -> 自变量 [指数]
    public Power parsePower() {
        String varName = lexer.peek();
        lexer.next();
        BigInteger exp = parseExponent();
        return new Power(varName, exp);
    }

    // 指数 -> '^' ['+'] 允许前导零的整数
    public BigInteger parseExponent() {
        if ("^".equals(lexer.peek())) {
            consume("^");
            while ("+".equals(lexer.peek())) {
                consume("+");
            }
            String exp = lexer.peek();
            lexer.next();
            return new BigInteger(exp);
        }
        return BigInteger.ONE;
    }

    // 表达式因子 -> '(' 表达式 ')' [指数]
    public Expr parseExprFactor() {
        consume("(");
        Expr expr = parseExpr();
        consume(")");
        expr.setExponent(parseExponent());
        return expr;
    }

    // 指数函数 -> 'exp' '(' 因子 ')' [指数]
    public ExpFactor parseExpFactor() {
        consume("exp");
        consume("(");
        Factor factor = parseFactor();
        consume(")");
        BigInteger exp = parseExponent();
        return new ExpFactor(factor, exp);
    }

    // 函数调用 -> 'f' '(' 因子 ')' | 'f' '{' 序号 '}' '(' 因子 ')'
    public FuncFactor parseFuncFactor() {
        Integer index = null;
        consume("f");
        if ("{".equals(lexer.peek())) {
            consume("{");
            index = Integer.valueOf(lexer.peek());
            lexer.next();
            consume("}");
        }
        consume("(");
        Factor factor = parseFactor();
        consume(")");
        return new FuncFactor(factor, index, registry);
    }

    // 选择式因子 -> '[' '(' 因子 '==' 因子 ')' '?' 因子 ':' 因子 ']'
    public ChoiceFactor parseChoiceFactor() {
        consume("[");
        consume("(");
        final Factor left = parseFactor();
        consume("==");
        final Factor right = parseFactor();
        consume(")");
        consume("?");
        final Factor whenTrue = parseFactor();
        consume(":");
        final Factor whenFalse = parseFactor();
        consume("]");
        return new ChoiceFactor(left, right, whenTrue, whenFalse);
    }
}