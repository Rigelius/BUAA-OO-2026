import java.math.BigInteger;

public class Parser {

    private Lexer lexer;

    private FuncReg registry;

    public Parser(Lexer lexer, FuncReg registry) {
        this.lexer = lexer;
        this.registry = registry;
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

    //因子 → 变量因子 | 常数因子 | 表达式因子 | 选择式因子
    private Factor parseFactor() {
        String s = lexer.peek();
        if ("exp".equals(s)) {
            return parseExpFactor();
        } else if ("f".equals(s)) {
            return parseFuncFactor();
        } else if ("[".equals(s)) {
            return parseChoiceFactor();
        } else if ("x".equals(s)) {
            return parsePower();
        } else if ("(".equals(s)) {
            return parseExprFactor();
        } else {
            return parseNumber();
        }
    }

    //常数因子 → 带符号的整数
    private Number parseNumber() {
        boolean negative = false;
        while ("+".equals(lexer.peek()) || "-".equals(lexer.peek())) {
            if ("-".equals(lexer.peek())) {
                negative = !negative;
            }
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
            BigInteger exp = parseExponent();
            return new Power("x", exp);
        }
        return null;
    }

    //指数 → ['^' ['+'] 整数]
    private BigInteger parseExponent() {
        if ("^".equals(lexer.peek())) {
            lexer.next();
            while ("+".equals(lexer.peek())) {
                lexer.next();
            }
            String exp = lexer.peek();
            lexer.next();
            return new BigInteger(exp);
        }
        return BigInteger.ONE;

    }

    //表达式因子 → '(' 表达式 ')' [指数]
    private Expr parseExprFactor() {
        if ("(".equals(lexer.peek())) {
            lexer.next();
            Expr expr = parseExpr();
            if (")".equals(lexer.peek())) {
                lexer.next();
            }
            expr.setExponent(parseExponent());
            return expr;
        }
        return null;
    }

    //指数函数因子 → exp '(' 因子 ')' [指数]
    private ExpFactor parseExpFactor() {
        if ("exp".equals(lexer.peek())) {
            lexer.next();
            if ("(".equals(lexer.peek())) {
                lexer.next();
            }
            Factor factor = parseFactor();
            if (")".equals(lexer.peek())) {
                lexer.next();
            }
            BigInteger exp = parseExponent();
            return new ExpFactor(factor, exp);
        }
        return null;
    }

    //函数调用因子 → f '(' 因子 ')'
    private FuncFactor parseFuncFactor() {
        if ("f".equals(lexer.peek())) {
            lexer.next();
            if ("(".equals(lexer.peek())) {
                lexer.next();
            }
            Factor factor = parseFactor();
            if (")".equals(lexer.peek())) {
                lexer.next();
            }
            return new FuncFactor(factor, registry.get("f"));
        }
        return null;
    }

    //选择式因子 → '[' '(' 因子 '==' 因子 ')' '?' 因子 ':' 因子 ']'
    private ChoiceFactor parseChoiceFactor() {
        if ("[".equals(lexer.peek())) {
            lexer.next();
            if ("(".equals(lexer.peek())) {
                lexer.next();
            }
            final Factor left = parseFactor();
            if ("==".equals(lexer.peek())) {
                lexer.next();
            }
            final Factor right = parseFactor();
            if (")".equals(lexer.peek())) {
                lexer.next();
            }
            if ("?".equals(lexer.peek())) {
                lexer.next();
            }
            final Factor whenTrue = parseFactor();
            if (":".equals(lexer.peek())) {
                lexer.next();
            }
            final Factor whenFalse = parseFactor();
            if ("]".equals(lexer.peek())) {
                lexer.next();
            }
            return new ChoiceFactor(left, right, whenTrue, whenFalse);
        }
        return null;
    }
}