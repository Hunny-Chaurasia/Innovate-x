// Normalize legacy event handlers to await the asynchronous API facade.
// This is an AST transform, not a text replacement of JavaScript syntax.
import ts from 'typescript';
import fs from 'node:fs';
import path from 'node:path';
const asynchronous = new Set(['createProject', 'addRequests', 'registerStudent', 'respondFunding', 'submitFunding', 'addReview', 'addReply', 'addProof', 'removeProof', 'publishProblem', 'markProblemSeen', 'toggleShortlist', 'respondCollab', 'setProfileEnabled', 'regenerateSlug']);
function transformFile(filename) {
  const source = ts.createSourceFile(filename, fs.readFileSync(filename, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  let changed = false;
  const result = ts.transform(source, [context => {
    let scope = null;
    function visit(node) {
      if (ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node) || ts.isArrowFunction(node) || ts.isMethodDeclaration(node)) {
        const parent = scope; scope = { await: false };
        const next = ts.visitEachChild(node, visit, context);
        const needs = scope.await; scope = parent;
        if (!needs || next.modifiers?.some(m => m.kind === ts.SyntaxKind.AsyncKeyword)) return next;
        changed = true;
        const modifiers = [...(next.modifiers || []), context.factory.createModifier(ts.SyntaxKind.AsyncKeyword)];
        if (ts.isArrowFunction(next)) return context.factory.updateArrowFunction(next, modifiers, next.typeParameters, next.parameters, next.type, next.equalsGreaterThanToken, next.body);
        if (ts.isFunctionDeclaration(next)) return context.factory.updateFunctionDeclaration(next, modifiers, next.asteriskToken, next.name, next.typeParameters, next.parameters, next.type, next.body);
        if (ts.isFunctionExpression(next)) return context.factory.updateFunctionExpression(next, modifiers, next.asteriskToken, next.name, next.typeParameters, next.parameters, next.type, next.body);
        return context.factory.updateMethodDeclaration(next, modifiers, next.asteriskToken, next.name, next.questionToken, next.typeParameters, next.parameters, next.type, next.body);
      }
      const next = ts.visitEachChild(node, visit, context);
      if (scope && ts.isCallExpression(node) && ts.isIdentifier(node.expression) && asynchronous.has(node.expression.text) && !ts.isAwaitExpression(node.parent)) {
        scope.await = true; changed = true; return context.factory.createAwaitExpression(next);
      }
      return next;
    }
    return root => ts.visitNode(root, visit);
  }]);
  if (changed) fs.writeFileSync(filename, ts.createPrinter().printFile(result.transformed[0]));
  result.dispose();
}
function walk(directory) { for (const file of fs.readdirSync(directory, { withFileTypes: true })) { const filename = path.join(directory, file.name); if (file.isDirectory()) walk(filename); else if (filename.endsWith('.tsx')) transformFile(filename); } }
walk('src/components');
walk('src/pages');
