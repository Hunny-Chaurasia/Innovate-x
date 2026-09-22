import reflex as rx

import re

EXPORTS = frozenset(
    "CONTACTS CURRENT_FACULTY CURRENT_INDUSTRY CURRENT_STUDENT CollabRequest FundingRecord FundingStatus InstitutionType NewCollabRequest Party Person ProblemStatement ProjectReview ProofAttachment ProofEntry RegisteredStudent RequestStatus ReviewReply ReviewStatus ShareProfile StudentProject TEAM_DIRECTORY TeamMember addProof addReply addRequests addReview createProject ensureProfile getTeamLeader isMemberOf latestFunding markProblemSeen publicProfileUrl publishProblem regenerateSlug registerStudent removeProof respondCollab respondFunding setProfileEnabled slugify submitFunding teamFormationRule timeAgo toggleShortlist useAllProblems useWorkflow".split()
)
ASYNC_EXPORTS = frozenset(
    "submitFunding respondFunding addReview addReply addProof removeProof publishProblem markProblemSeen toggleShortlist createProject addRequests respondCollab setProfileEnabled regenerateSlug registerStudent".split()
)
TOKEN = re.compile(
    r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|[A-Za-z_$][\w$]*|=>|\S'
)


def archive_exports(source: str) -> set[str]:
    return set(
        re.findall(
            r"export\s+(?:const|let|function|interface|type|class)\s+([A-Za-z_$][\w$]*)",
            source,
        )
    )


def patch_shells(source: str) -> tuple[str, str]:
    pattern = r"import\s*\{\s*MOCK_USERS\s*\}\s*from\s*[\"\']([^\"\']+)[\"\'];?"
    imports = list(re.finditer(pattern, source))
    if len(imports) != 1:
        raise ValueError("Archive MOCK_USERS import contract changed")
    module = imports[0].group(1)
    if not module.startswith("./"):
        raise ValueError("Expected relative shell identity import")
    contract = f'export type ShellUser = (typeof import(".{module}"))["MOCK_USERS"]["student"];\n'
    source = re.sub(
        pattern, 'import { currentShellUser } from "./live/api";', source
    )
    for role in ("student", "faculty", "industry", "admin"):
        old = f"user={{MOCK_USERS.{role}}}"
        if source.count(old) != 1:
            raise ValueError(f"Archive {role} shell contract changed")
        source = source.replace(old, f'user={{currentShellUser("{role}")}}')
    if "MOCK_USERS" in source:
        raise ValueError("Unrecognized shell demo identity reference")
    return source, contract


def await_workflow_calls(source: str) -> str:
    """Mechanical async adaptation; never changes business expressions or routes."""
    if not re.search(r"from\s*[\"\'][^\"\']*store/workflow[\"\']", source):
        return source
    tokens = [
        m
        for m in TOKEN.finditer(source)
        if not m.group().startswith(("//", "/*"))
    ]
    pairs: dict[int, int] = {}
    stack: list[int] = []
    parents: dict[int, list[int]] = {}
    for i, token in enumerate(tokens):
        parents[i] = stack.copy()
        value = token.group()
        if value in ("(", "{", "["):
            stack.append(i)
        elif value in (")", "}", "]") and stack:
            opening = stack.pop()
            pairs[i] = opening
            pairs[opening] = i
    edits: dict[int, str] = {}
    for i, token in enumerate(tokens):
        if (
            token.group() not in ASYNC_EXPORTS
            or i + 1 >= len(tokens)
            or tokens[i + 1].group() != "("
        ):
            continue
        if i and tokens[i - 1].group() in ("await", ".", "function"):
            continue
        # An expression-bodied callback already returns the mutation promise.
        if i and tokens[i - 1].group() == "=>":
            continue
        boundary = None
        for opening in reversed(parents[i]):
            if tokens[opening].group() != "{" or opening == 0:
                continue
            before = opening - 1
            if tokens[before].group() == "=>":
                start = before - 1
                if tokens[start].group() == ")":
                    start = pairs[start]
                boundary = (opening, start)
                break
            if tokens[before].group() == ")":
                left = pairs.get(before, before)
                name = left - 1
                if name >= 1 and tokens[name - 1].group() == "function":
                    boundary = (opening, name - 1)
                    break
        if boundary is None:
            raise ValueError(
                f"Unsupported synchronous workflow call: {token.group()}"
            )
        opening, start = boundary
        if start > 0 and tokens[start - 1].group() != "async":
            edits[tokens[start].start()] = "async "
        edits[token.start()] = "await "
    for position in sorted(edits, reverse=True):
        source = f"{source[:position]}{edits[position]}{source[position:]}"
    return source
