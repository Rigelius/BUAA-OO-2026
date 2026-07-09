import java.math.BigInteger;

public class Parser {

    private Lexer lexer;

    public Parser(Lexer lexer) {
        this.lexer = lexer;
    }

    //表达式 → [加减] 项 { 加减 项 }
    public Expr parseExpr() {
        Expr expr = new Expr();
        expr.addTerm(parseTerm());

        while ("+".equals(lexer.peek()) || "-".equals(lexer.peek())) {
            boolean flg = "-".equals(lexer.peek());
            lexer.next();
            Term term = parseTerm();
            if (flg) {
                term.negate();
            }
            expr.addTerm(term);

        }
        return expr;
    }

    //项 → [加减] 因子 { '*' 因子 }
    private Term parseTerm() {
        Term term = new Term();

        boolean negative = false;
        while ("+".equals(lexer.peek()) || "-".equals(lexer.peek())) {
            if ("-".equals(lexer.peek())) {
                negative = !negative;
            }
            lexer.next();
        }

        term.addFactor(parseFactor());
        if (negative) {
            term.negate();
        }

        while ("*".equals(lexer.peek())) {
            lexer.next();
            term.addFactor(parseFactor());
        }
        return term;
    }

    //因子 → 变量因子 | 常数因子 | 表达式因子
    private Factor parseFactor() {
        String s = lexer.peek();
        if ("x".equals(s)) {
            return parsePower();
        } else if ("(".equals(s)) {
            lexer.next();
            Expr expr = parseExpr();
            if (")".equals(lexer.peek())) {
                lexer.next();
            }
            expr.setExponent(parseExponent());
            return expr;
        } else {
            return parseNumber();
        }
    }

    //常数因子 → 带符号的整数
    private Number parseNumber() {
        boolean negative = false;
        if ("+".equals(lexer.peek())) {
            lexer.next();
        } else if ("-".equals(lexer.peek())) {
            negative = true;
            lexer.next();
        }

        BigInteger num = new BigInteger(lexer.peek());
        if (negative) {
            num = num.negate();
        }
        lexer.next();
        return new Number(num);
    }

    //变量因子 → x[^指数]
    private Power parsePower() {
        if ("x".equals(lexer.peek())) {
            lexer.next();
            int exp = parseExponent();
            return new Power("x", exp);
        }
        return null;
    }

    //指数 → ['^' ['+'] 整数]
    private int parseExponent() {
        if ("^".equals(lexer.peek())) {
            lexer.next();
            if ("+".equals(lexer.peek())) {
                lexer.next();
            }
            String exp = lexer.peek();
            lexer.next();
            return Integer.parseInt(exp);
        }
        return 1;
    }
}