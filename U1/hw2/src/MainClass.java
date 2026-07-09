import java.math.BigInteger;
import java.util.HashMap;
import java.util.Map;
import java.util.Scanner;

public class MainClass {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        FuncReg registry = new FuncReg();

        int n = Integer.parseInt(sc.nextLine().trim());
        for (int i = 0; i < n; i++) {
            String funcLine = Processor.preprocess(sc.nextLine());
            String[] parts = funcLine.split("=", 2);
            String head = parts[0];
            String body = parts[1];
            String funcName = head.substring(0, head.indexOf('('));

            Lexer bodyLexer = new Lexer(body);
            Parser bodyParser = new Parser(bodyLexer, registry);
            Expr bodyExpr = bodyParser.parseExpr();
            FuncReg.FuncDef funcDef = new FuncReg.FuncDef(funcName, bodyExpr);
            registry.put(funcDef);
        }

        String s = sc.nextLine();
        s = Processor.preprocess(s);
        Lexer lexer = new Lexer(s);
        Parser parser = new Parser(lexer, registry);
        Expr expr = parser.parseExpr();
        Map<String, Poly> vars = new HashMap<>();
        vars.put("x", new Poly(new Mono(BigInteger.ONE, BigInteger.ONE, Poly.ZERO)));
        Poly poly = expr.toPoly(vars);
        System.out.println(poly);
    }
}